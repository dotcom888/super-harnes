# -*- coding: utf-8 -*-
import json
import logging
from typing import List, Optional, Set, Dict, Any
from openai import OpenAI
from context.window import TurnChunk
from context.token_counter import TokenCounter, default_token_counter

logger = logging.getLogger(__name__)

COMPACTION_SYSTEM_PROMPT = """你是一个专业的代码排查与修改上下文压缩器。
你的任务是将以下被淘汰的早期对话历史提炼为一份高密度的《历史排查与修改纪要》（300字以内）。
要求：
1. 提取已排查的代码文件、函数与结论（确认无误的模块，防止后续重复排查）；
2. 提取已经进行的代码修改、涉及文件与结果；
3. 提取执行的命令、测试结果及遗留的异常报错；
4. 提取用户给出的关键偏好、约束或目标转变；
5. 剔除寒暄、长篇日志与试探性输出，仅保留确定的工程事实。
如果提供了上一次的纪要，请将新信息与旧纪要合并更新。
"""

class SummaryState:
    """
    摘要状态与区间锚点：
    明确记录本摘要总结了从第几轮到第几轮的历史（Range Tracking）。
    """
    def __init__(self):
        self.summary_text: str = ""
        self.start_turn_id: int = 0
        self.end_turn_id: int = 0
        self.covered_through_turn_id: int = 0
        self.last_summarized_turn_count: int = 0

    def has_summary(self) -> bool:
        return bool(self.summary_text and self.summary_text.strip())

    def get_range_header(self) -> str:
        if not self.has_summary():
            return ""
        return f"【历史排查与修改纪要 (已覆盖轮次 #{self.start_turn_id} ~ #{self.end_turn_id})】"

    def to_dict(self):
        return {
            "summary_text": self.summary_text,
            "start_turn_id": self.start_turn_id,
            "end_turn_id": self.end_turn_id,
            "covered_through_turn_id": self.covered_through_turn_id,
            "last_summarized_turn_count": self.last_summarized_turn_count
        }

    def load_dict(self, data: dict):
        if not isinstance(data, dict):
            return
        self.summary_text = str(data.get("summary_text", ""))
        self.start_turn_id = int(data.get("start_turn_id", 0))
        self.end_turn_id = int(data.get("end_turn_id", 0))
        self.covered_through_turn_id = int(data.get("covered_through_turn_id", 0))
        self.last_summarized_turn_count = int(data.get("last_summarized_turn_count", 0))

    def clear(self):
        self.summary_text = ""
        self.start_turn_id = 0
        self.end_turn_id = 0
        self.covered_through_turn_id = 0
        self.last_summarized_turn_count = 0


class ContextSummarizer:
    """
    历史排查摘要器：
    内置“区间锚点记录”、“入参感知”与“双模压缩（大模型深度压缩 + 即时规则补偿）”。
    """
    def __init__(
        self,
        client: Optional[OpenAI] = None,
        model: Optional[str] = None,
        min_turn_delta: int = 3,
        min_token_delta: int = 1500,
        cooldown_turns: int = 2,
        request_timeout: float = 15.0
    ):
        self.client = client
        self.model = model or "deepseek-chat"
        self.min_turn_delta = min_turn_delta
        self.min_token_delta = min_token_delta
        self.cooldown_turns = cooldown_turns
        self.request_timeout = request_timeout
        self.state = SummaryState()

    @property
    def current_summary(self) -> str:
        return self.state.summary_text

    def should_summarize(
        self,
        newly_evicted_chunks: List[TurnChunk],
        current_turn_id: int,
        counter: TokenCounter = default_token_counter,
        force: bool = False
    ) -> bool:
        """
        大模型深度摘要防抖判定（Debounce Guard）：
        防止水位在边界反复跳变导致频繁进行耗时的大模型异步/同步调用。
        """
        if not newly_evicted_chunks:
            return False

        if force:
            return True

        uncompacted = [c for c in newly_evicted_chunks if c.turn_id > self.state.covered_through_turn_id]
        if not uncompacted:
            return False

        if len(uncompacted) < self.min_turn_delta:
            return False

        uncompacted_tokens = sum(c.estimate_tokens(counter) for c in uncompacted)
        if uncompacted_tokens < self.min_token_delta:
            return False

        if self.state.last_summarized_turn_count > 0:
            if (current_turn_id - self.state.last_summarized_turn_count) < self.cooldown_turns:
                return False

        return True

    def _format_preview(self, content: Any, max_len: int = 300) -> str:
        text = str(content) if content is not None else ""
        if len(text) <= max_len:
            return text
        head = text[: int(max_len * 0.7)]
        tail = text[-int(max_len * 0.3):]
        return f"{head}...[省略 {len(text) - max_len} 字符]...{tail}"

    def _extract_tool_args_summary(self, raw_args: Any) -> str:
        """从 tool 调用参数中提炼关键工程路径与命令，防止摘要失真"""
        if not raw_args:
            return ""
        args_dict = {}
        if isinstance(raw_args, dict):
            args_dict = raw_args
        elif isinstance(raw_args, str):
            try:
                args_dict = json.loads(raw_args)
            except Exception:
                return raw_args[:60]

        parts = []
        for k in ["file_path", "path", "command", "cmd", "pattern", "query"]:
            if k in args_dict and args_dict[k]:
                parts.append(f"{k}='{str(args_dict[k])[:60]}'")
        return f"({', '.join(parts)})" if parts else ""

    def _fallback_heuristic_summary(self, evicted_chunks: List[TurnChunk], previous_summary: str) -> str:
        """强化规则兜底摘要：提取意图轨迹、调用工具+入参、关键文件及执行状态"""
        touched_files: Set[str] = set()
        user_queries: List[str] = []
        actions_taken: List[str] = []
        errors_found: List[str] = []

        for chunk in evicted_chunks:
            for msg in chunk.messages:
                role = msg.get("role")
                if role == "user":
                    content = str(msg.get("content", "")).strip()
                    if content and not content.startswith("【工作区感知状态"):
                        user_queries.append(content[:80])
                elif role == "assistant" and msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        if isinstance(tc, dict):
                            func = tc.get("function", {})
                            fname = func.get("name", "")
                            args_str = self._extract_tool_args_summary(func.get("arguments"))
                            if fname:
                                actions_taken.append(f"{fname}{args_str}")
                elif role == "tool":
                    c = str(msg.get("content", ""))
                    if any(w in c for w in ["Error", "Exception", "失败", "FAILED", "Errno"]):
                        err_line = next((line for line in c.splitlines() if any(w in line for w in ["Error", "Exception", "失败", "FAILED"])), "")
                        if err_line:
                            errors_found.append(err_line[:100].strip())
                    for token in c.split():
                        clean_token = token.strip("`'\",:;()[]{}")
                        if any(clean_token.endswith(ext) for ext in [".py", ".ts", ".js", ".json", ".md", ".toml", ".yaml"]):
                            touched_files.add(clean_token)

        lines = []
        if previous_summary:
            lines.append(f"【前期纪要】: {self._format_preview(previous_summary, 120)}")
        if user_queries:
            lines.append(f"- 意图演进: {' -> '.join(user_queries[-3:])}")
        if actions_taken:
            lines.append(f"- 历史操作: {'; '.join(actions_taken[-5:])}")
        if touched_files:
            lines.append(f"- 关键涉及文件: {', '.join(sorted(touched_files)[:6])}")
        if errors_found:
            lines.append(f"- 遗留排查异常: {errors_found[-1]}")

        return "\n".join(lines) if lines else "（已完成早期多轮代码排查与修改）"

    def summarize(
        self,
        newly_evicted_chunks: List[TurnChunk],
        current_turn_id: int,
        client: Optional[OpenAI] = None,
        model: Optional[str] = None,
        use_llm: bool = True
    ) -> str:
        """
        执行增量摘要压缩，并原子更新区间锚点（Range Tracking）。
        如果 use_llm=False，则采用即时轻量规则补偿（用于消除防抖期间的信息黑洞）。
        """
        if not newly_evicted_chunks:
            return self.state.summary_text

        uncompacted = [c for c in newly_evicted_chunks if c.turn_id > self.state.covered_through_turn_id]
        if not uncompacted:
            return self.state.summary_text

        chunk_ids = [c.turn_id for c in uncompacted]
        min_id = min(chunk_ids)
        max_id = max(chunk_ids)

        active_client = client or self.client
        active_model = model or self.model

        generated_summary = ""

        if use_llm and active_client:
            formatted_history = []
            for chunk in uncompacted:
                formatted_history.append(f"--- 轮次 #{chunk.turn_id} ---")
                for msg in chunk.messages:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if msg.get("tool_calls"):
                        tool_descs = []
                        for tc in msg["tool_calls"]:
                            if isinstance(tc, dict):
                                func = tc.get("function", {})
                                name = func.get("name", "unknown")
                                args_preview = self._extract_tool_args_summary(func.get("arguments"))
                                tool_descs.append(f"{name}{args_preview}")
                        formatted_history.append(f"assistant (调用工具): {', '.join(tool_descs)}")
                    elif role == "tool":
                        preview = self._format_preview(content, 250)
                        formatted_history.append(f"tool_result: {preview}")
                    else:
                        preview = self._format_preview(content, 200)
                        formatted_history.append(f"{role}: {preview}")

            history_text = "\n".join(formatted_history)
            try:
                user_prompt = (
                    f"这是前期的排查纪要（覆盖到 #{self.state.covered_through_turn_id} 轮）：\n{self.state.summary_text or '（无）'}\n\n"
                    f"这是本次新增淘汰的轮次（#{min_id} ~ #{max_id}）：\n{history_text}\n\n"
                    f"请输出最新的《历史排查与修改纪要》："
                )
                resp = active_client.chat.completions.create(
                    model=active_model,
                    messages=[
                        {"role": "system", "content": COMPACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=500,
                    temperature=0.3,
                    timeout=self.request_timeout
                )
                if resp and resp.choices and resp.choices[0].message:
                    ans = resp.choices[0].message.content
                    if ans and ans.strip():
                        generated_summary = ans.strip()[:400]
            except Exception as e:
                logger.warning(f"大模型历史摘要调用失败，执行规则补偿: {e}")

        if not generated_summary:
            generated_summary = self._fallback_heuristic_summary(uncompacted, self.state.summary_text)

        # 原子更新区间锚点与状态
        if self.state.start_turn_id == 0:
            self.state.start_turn_id = min_id
        self.state.end_turn_id = max_id
        self.state.covered_through_turn_id = max_id
        if use_llm:
            self.state.last_summarized_turn_count = current_turn_id
        self.state.summary_text = generated_summary

        return self.state.summary_text

    def clear(self):
        self.state.clear()
