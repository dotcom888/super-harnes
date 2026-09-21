# -*- coding: utf-8 -*-
import re
from typing import Dict, Any, List, Optional

# 尝试可选加载 tiktoken
_TIKTOKEN_ENCODER = None
try:
    import tiktoken
    try:
        _TIKTOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")
    except Exception:
        pass
except ImportError:
    pass

class TokenCounter:
    """
    高精度 Token 计数与上下文使用率计算器：
    1. 优先使用 tiktoken (cl100k_base / o200k_base) 真实编码；
    2. 无外部库时，采用高精度分词加权估算（区分 CJK 中文、代码标点、空白缩进与英文单词）；
    3. 严格遵循 OpenAI 消息格式规范计算 role, name, tool_calls, tool_call_id 等开销；
    4. 健壮兼容字典 (dict) 与 Pydantic 对象 (如 ChatCompletionMessage)。
    """
    def __init__(self, char_per_token: Optional[float] = None):
        self.char_per_token = char_per_token
        self._encoder = _TIKTOKEN_ENCODER

    def count_text(self, text: str) -> int:
        """估算纯文本的 Token 开销"""
        if not text:
            return 0

        # 若环境已安装并成功加载 tiktoken，则直接精确编码
        if self._encoder is not None:
            try:
                return len(self._encoder.encode(text))
            except Exception:
                pass

        # 若用户显式指定了传统的 char_per_token，且非默认启发式，则保持兼容
        if self.char_per_token is not None and self.char_per_token > 0:
            return max(1, int(len(text) / self.char_per_token))

        # 高精度加权估算器：
        # - CJK 中日韩字符: 平均约 1.35 tokens/字符
        # - 代码标点与符号: 约 0.85 tokens/符号
        # - 换行与连续空白缩进: 约 0.75 tokens/个
        # - 英文单词与数字: 约 3.8 字符/token
        cjk_count = len(re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', text))
        code_punct_count = len(re.findall(r'[{}\[\]();:.,<>=\+\-\*/\\`\'\"_\|\&\!\?\%\^~#@$]', text))
        newline_count = text.count('\n')
        
        remaining_text = re.sub(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef{}\[\]();:.,<>=\+\-\*/\\`\'\"_\|\&\!\?\%\^~#@$\n]', ' ', text)
        words = remaining_text.split()
        word_tokens = sum(max(1, int(len(w) / 3.8 + 0.5)) for w in words)

        estimated = (
            int(cjk_count * 1.35) +
            int(code_punct_count * 0.85) +
            int(newline_count * 0.75) +
            word_tokens
        )
        return max(1, estimated)

    def _normalize_message(self, msg: Any) -> Dict[str, Any]:
        """将各类消息对象（dict, ChatCompletionMessage 等）归一化为安全字典"""
        if isinstance(msg, dict):
            return msg
        if hasattr(msg, "model_dump"):
            try:
                return msg.model_dump()
            except Exception:
                pass
        if hasattr(msg, "to_dict"):
            try:
                return msg.to_dict()
            except Exception:
                pass

        # 通用反射属性提取
        normalized: Dict[str, Any] = {
            "role": getattr(msg, "role", ""),
            "content": getattr(msg, "content", ""),
        }
        if hasattr(msg, "tool_calls") and getattr(msg, "tool_calls"):
            raw_tcs = getattr(msg, "tool_calls")
            clean_tcs = []
            for tc in raw_tcs:
                if isinstance(tc, dict):
                    clean_tcs.append(tc)
                elif hasattr(tc, "model_dump"):
                    clean_tcs.append(tc.model_dump())
                else:
                    func = getattr(tc, "function", None)
                    func_dict = {
                        "name": getattr(func, "name", "") if func else "",
                        "arguments": getattr(func, "arguments", "") if func else ""
                    }
                    clean_tcs.append({
                        "id": getattr(tc, "id", ""),
                        "type": getattr(tc, "type", "function"),
                        "function": func_dict
                    })
            normalized["tool_calls"] = clean_tcs

        if hasattr(msg, "tool_call_id") and getattr(msg, "tool_call_id"):
            normalized["tool_call_id"] = getattr(msg, "tool_call_id")
        if hasattr(msg, "name") and getattr(msg, "name"):
            normalized["name"] = getattr(msg, "name")

        return normalized

    def count_message(self, msg: Any) -> int:
        """
        估算单条 OpenAI 协议消息的 Token 开销：
        遵循 OpenAI 消息结构开销：
        每条消息的基础定界符 (role + boundary) 约 3~4 tokens
        """
        safe_msg = self._normalize_message(msg)
        tokens = 3  # <|im_start|>{role}\n ... <|im_end|>

        role = safe_msg.get("role", "")
        if role:
            tokens += self.count_text(str(role))

        name = safe_msg.get("name")
        if name:
            tokens += self.count_text(str(name)) + 1

        content = safe_msg.get("content")
        if content:
            if isinstance(content, str):
                tokens += self.count_text(content)
            elif isinstance(content, list):
                # 多模态消息列表格式兼容
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            tokens += self.count_text(item.get("text", ""))
                        elif item.get("type") == "image_url":
                            tokens += 85
                    else:
                        tokens += self.count_text(str(item))
            else:
                tokens += self.count_text(str(content))

        # tool_call_id (for role == "tool")
        tool_call_id = safe_msg.get("tool_call_id")
        if tool_call_id:
            tokens += self.count_text(str(tool_call_id)) + 2

        # assistant 发起的 tool_calls
        tool_calls = safe_msg.get("tool_calls")
        if tool_calls and isinstance(tool_calls, list):
            for tc in tool_calls:
                tokens += 3  # tool_call item delimiter
                if isinstance(tc, dict):
                    tc_id = tc.get("id", "")
                    if tc_id:
                        tokens += self.count_text(str(tc_id))
                    func = tc.get("function", {})
                    if isinstance(func, dict):
                        func_name = func.get("name", "")
                        func_args = func.get("arguments", "")
                        tokens += self.count_text(str(func_name))
                        tokens += self.count_text(str(func_args))
                        tokens += 4  # JSON encapsulation overhead

        return tokens

    def count_messages(self, messages: List[Any]) -> int:
        """计算消息列表总 Token，加上会话引导开销"""
        if not messages:
            return 0
        total = sum(self.count_message(m) for m in messages)
        # 对话末尾引导符 <|im_start|>assistant
        total += 3
        return total

    def get_utilization(self, current_tokens: int, max_budget_tokens: int) -> float:
        """计算当前 Context 的水位使用率 (0.0 ~ 1.0+)"""
        if max_budget_tokens <= 0:
            return 1.0
        return round(current_tokens / max_budget_tokens, 4)

default_token_counter = TokenCounter()
