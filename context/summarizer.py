# -*- coding: utf-8 -*-
import json
from typing import List, Optional
from openai import OpenAI
from context.window import TurnChunk
from context.token_counter import TokenCounter, default_token_counter

COMPACTION_SYSTEM_PROMPT = """你是一个专业的代码排查与修改上下文压缩器。
你的任务是将以下被淘汰的早期对话历史提炼为一份高密度的《历史排查与修改纪要》（300字以内）。
要求：
1. 提取已排查的代码文件与结论（确认无误的模块，防止后续重复排查）；
2. 提取已经进行的代码修改与涉及文件；
3. 提取用户给出的关键偏好、约束或目标转变；
4. 剔除寒暄、长篇日志与中间试探性输出，仅保留确定的工程事实。
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

    def clear(self):
        self.summary_text = ""
        self.start_turn_id = 0
        self.end_turn_id = 0
        self.covered_through_turn_id = 0
        self.last_summarized_turn_count = 0


class ContextSummarizer:
    """
    历史排查摘要器：
    内置“区间锚点记录”与“防摘要抖动机制 (Anti-Jitter Debounce)”。
    """
    def __init__(
        self,
        client: Optional[OpenAI] = None,
        model: str = "deepseek-chat",
        min_turn_delta: int = 3,
        min_token_delta: int = 1500,
        cooldown_turns: int = 2
    ):
        self.client = client
        self.model = model
        self.min_turn_delta = min_turn_delta
        self.min_token_delta = min_token_delta
        self.cooldown_turns = cooldown_turns
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
        防抖判定（Debounce Guard）：
        防止水位在 75% 边界反复跳变导致频繁调用大模型做摘要。
        必须同时满足：
        1. 存在未被总结过的新淘汰轮次；
        2. 新增淘汰轮数 >= min_turn_delta (默认 3 轮)；
        3. 新增淘汰总 Token >= min_token_delta (默认 1500 Tokens)；
        4. 冷却周期：距上次摘要完成已走过 cooldown_turns (默认 2 轮)。
        """
        if not newly_evicted_chunks:
            return False

        if force:
            return True

        # 过滤出尚未被总结过的块（turn_id > covered_through_turn_id）
        uncompacted = [c for c in newly_evicted_chunks if c.turn_id > self.state.covered_through_turn_id]
        if not uncompacted:
            return False

        # 条件 1: 最小新增轮数限制
        if len(uncompacted) < self.min_turn_delta:
            return False

        # 条件 2: 最小新增 Token 限制
        uncompacted_tokens = sum(c.estimate_tokens(counter) for c in uncompacted)
        if uncompacted_tokens < self.min_token_delta:
            return False

        # 条件 3: 冷却轮数防抖
        if self.state.last_summarized_turn_count > 0:
            if (current_turn_id - self.state.last_summarized_turn_count) < self.cooldown_turns:
                return False

        return True

    def _fallback_heuristic_summary(self, evicted_chunks: List[TurnChunk], previous_summary: str) -> str:
        """规则兜底摘要"""
        touched_files = set()
        user_queries = []

        for chunk in evicted_chunks:
            for msg in chunk.messages:
                role = msg.get("role")
                if role == "user":
                    content = str(msg.get("content", "")).strip()
                    if content:
                        user_queries.append(content[:60])
                elif role == "tool":
                    c = str(msg.get("content", ""))
                    if "文件" in c or "tools/" in c or ".py" in c:
                        for token in c.split():
                            if ".py" in token or "/" in token:
                                touched_files.add(token.strip("`'\"，。:;"))

        lines = []
        if previous_summary:
            lines.append(f"【前期纪要】: {previous_summary[:120]}...")
        if user_queries:
            lines.append(f"- 排查意图轨迹: {' -> '.join(user_queries[-3:])}")
        if touched_files:
            lines.append(f"- 涉及关键文件: {', '.join(list(touched_files)[:6])}")

        return "\n".join(lines) if lines else "（已完成早期多轮代码排查）"

    def summarize(
        self,
        newly_evicted_chunks: List[TurnChunk],
        current_turn_id: int,
        client: Optional[OpenAI] = None,
        model: Optional[str] = None
    ) -> str:
        """
        执行增量摘要压缩，并原子更新区间锚点（Range Tracking）。
        """
        if not newly_evicted_chunks:
            return self.state.summary_text

        # 找出本次参与压缩的轮次区间
        chunk_ids = [c.turn_id for c in newly_evicted_chunks]
        min_id = min(chunk_ids)
        max_id = max(chunk_ids)

        active_client = client or self.client
        active_model = model or self.model

        formatted_history = []
        for chunk in newly_evicted_chunks:
            formatted_history.append(f"--- 轮次 #{chunk.turn_id} ---")
            for msg in chunk.messages:
                role = msg.get("role")
                content = msg.get("content", "")
                if msg.get("tool_calls"):
                    tool_names = [tc['function']['name'] for tc in msg['tool_calls']]
                    formatted_history.append(f"assistant (调用工具): {', '.join(tool_names)}")
                elif role == "tool":
                    preview = (str(content)[:120] + "...") if len(str(content)) > 120 else str(content)
                    formatted_history.append(f"tool_result: {preview}")
                else:
                    preview = (str(content)[:120] + "...") if len(str(content)) > 120 else str(content)
                    formatted_history.append(f"{role}: {preview}")

        history_text = "\n".join(formatted_history)
        generated_summary = ""

        if active_client:
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
                    max_tokens=600,
                    temperature=0.3
                )
                ans = resp.choices[0].message.content
                if ans and ans.strip():
                    generated_summary = ans.strip()
            except Exception:
                pass

        if not generated_summary:
            generated_summary = self._fallback_heuristic_summary(newly_evicted_chunks, self.state.summary_text)

        # 原子更新区间锚点
        if self.state.start_turn_id == 0:
            self.state.start_turn_id = min_id
        self.state.end_turn_id = max_id
        self.state.covered_through_turn_id = max_id
        self.state.last_summarized_turn_count = current_turn_id
        self.state.summary_text = generated_summary

        return self.state.summary_text

    def clear(self):
        self.state.clear()
