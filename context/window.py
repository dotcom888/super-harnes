# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Tuple, Set
from context.token_counter import TokenCounter, default_token_counter

class TurnChunk:
    """
    原子轮次块 (TurnChunk):
    将一次完整的交互及其内部的所有 ReAct 工具调用、参数、结果与回答打包。
    严格保证 tool_calls 与 tool 结果成对绑定，不可拆分。
    """
    def __init__(self, turn_id: int):
        self.turn_id = turn_id
        self.messages: List[Dict[str, Any]] = []

    def add_message(self, msg: Dict[str, Any]):
        self.messages.append(msg)

    def estimate_tokens(self, counter: TokenCounter = default_token_counter) -> int:
        return counter.count_messages(self.messages)

    def get_tool_call_ids(self) -> Set[str]:
        """获取本轮中 assistant 发起的所有 tool_call_id"""
        call_ids = set()
        for msg in self.messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    if isinstance(tc, dict) and tc.get("id"):
                        call_ids.add(tc["id"])
        return call_ids

    def get_tool_result_ids(self) -> Set[str]:
        """获取本轮中 tool 消息所对应的 tool_call_id"""
        result_ids = set()
        for msg in self.messages:
            if msg.get("role") == "tool" and msg.get("tool_call_id"):
                result_ids.add(msg["tool_call_id"])
        return result_ids

    def is_paired_and_complete(self) -> bool:
        """
        双向成对闭合校验：
        1. 所有 assistant 发起的 tool_calls 均有对应的 tool 结果回填；
        2. 所有 tool 结果均有对应的 assistant tool_calls，绝无孤立调用或悬挂结果。
        """
        calls = self.get_tool_call_ids()
        results = self.get_tool_result_ids()
        return calls == results

    def sanitize_unpaired_calls(self):
        """
        双向安全清洗：
        1. 清理有调用无结果的 tool_calls；
        2. 清理有结果无调用的孤立 tool 消息；
        3. 若 assistant 被清洗后既无 tool_calls 又无 content，提供默认占位符，防止 API 400 校验异常。
        """
        calls = self.get_tool_call_ids()
        results = self.get_tool_result_ids()

        unpaired_calls = calls - results
        unpaired_results = results - calls

        # 1. 清理孤立的 tool 消息
        if unpaired_results:
            self.messages = [
                m for m in self.messages
                if not (m.get("role") == "tool" and m.get("tool_call_id") in unpaired_results)
            ]

        # 2. 清理无结果的 tool_calls 并保障 assistant 消息合法性
        if unpaired_calls:
            for msg in self.messages:
                if msg.get("role") == "assistant" and msg.get("tool_calls"):
                    msg["tool_calls"] = [
                        tc for tc in msg["tool_calls"]
                        if tc.get("id") not in unpaired_calls
                    ]
                    if not msg["tool_calls"]:
                        del msg["tool_calls"]
                        if not str(msg.get("content", "")).strip():
                            msg["content"] = "（已执行工具操作）"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "messages": self.messages
        }


class SlidingWindow:
    """
    滑动窗口执行器：
    执行倒序贪心装入。当预算受限时，将历史轮次切分为：
    - active_chunks: 装入当前 LLM 上下文的活跃轮次（严格时间正序、连续无穿孔）
    - evicted_chunks: 因超预算被淘汰出的较早轮次（待进入摘要压缩器，严格时间正序）
    """
    def __init__(self, token_counter: TokenCounter = default_token_counter):
        self.token_counter = token_counter

    def split_by_budget(
        self,
        completed_turns: List[TurnChunk],
        budget_tokens: int
    ) -> Tuple[List[TurnChunk], List[TurnChunk]]:
        """
        根据剩余预算切分活跃轮次与淘汰轮次：
        从最新轮次向前倒序装载。
        关键保障：
        1. 修复穿孔 Bug：一旦遇到超出预算即刻截断；
        2. 防全损截断（Graceful Fallback）：如果最新一轮单独就超出预算，仍优先保留该最新一轮，
           避免活跃窗口被彻底清空（后续由硬门禁或消息裁剪进行安全压缩）。
        """
        if not completed_turns:
            return [], []

        active_chunks_rev: List[TurnChunk] = []
        cutoff_index = -1
        remaining = max(0, budget_tokens)

        total_turns = len(completed_turns)
        for i in range(total_turns - 1, -1, -1):
            chunk = completed_turns[i]
            chunk_tokens = chunk.estimate_tokens(self.token_counter)
            if chunk_tokens <= remaining:
                active_chunks_rev.append(chunk)
                remaining -= chunk_tokens
            else:
                cutoff_index = i
                break

        # 防全损保护：若预算极端紧张导致连最新一轮都无法放入，保留最近的 1 轮
        if not active_chunks_rev and total_turns > 0:
            latest_chunk = completed_turns[-1]
            active_chunks_rev.append(latest_chunk)
            cutoff_index = total_turns - 2

        if cutoff_index < 0:
            evicted_chunks = []
        else:
            evicted_chunks = completed_turns[:cutoff_index + 1]

        active_chunks = list(reversed(active_chunks_rev))
        return active_chunks, evicted_chunks
