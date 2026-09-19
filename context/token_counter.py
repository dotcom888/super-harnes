# -*- coding: utf-8 -*-
from typing import Dict, Any, List

class TokenCounter:
    """
    Token 计数与上下文使用率计算器：
    针对代码工程、中英文与工具调用的混合场景进行加权估算。
    """
    def __init__(self, char_per_token: float = 2.8):
        self.char_per_token = char_per_token

    def count_text(self, text: str) -> int:
        """估算纯文本的 Token 开销"""
        if not text:
            return 0
        return max(1, int(len(text) / self.char_per_token))

    def count_message(self, msg: Dict[str, Any]) -> int:
        """估算单条 OpenAI 协议消息的 Token 开销（含 role, content 与 tool_calls 结构）"""
        # 每条消息的基础格式与定界符开销
        tokens = 4
        
        content = msg.get("content")
        if content:
            tokens += self.count_text(str(content))
            
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                func = tc.get("function", {})
                tokens += self.count_text(func.get("name", ""))
                tokens += self.count_text(func.get("arguments", ""))
                tokens += 8  # tool_call id and structure overhead
                
        return tokens

    def count_messages(self, messages: List[Dict[str, Any]]) -> int:
        """计算消息列表总 Token"""
        return sum(self.count_message(m) for m in messages)

    def get_utilization(self, current_tokens: int, max_budget_tokens: int) -> float:
        """计算当前 Context 的水位使用率 (0.0 ~ 1.0+)"""
        if max_budget_tokens <= 0:
            return 1.0
        return round(current_tokens / max_budget_tokens, 4)

default_token_counter = TokenCounter()
