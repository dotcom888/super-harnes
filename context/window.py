# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Tuple
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "messages": self.messages
        }


class SlidingWindow:
    """
    滑动窗口执行器：
    执行倒序贪心装入。当预算受限时，将历史轮次切分为：
    - active_chunks: 装入当前 LLM 上下文的活跃轮次（正序排列）
    - evicted_chunks: 因超预算被淘汰出的较早轮次（待进入摘要压缩器）
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
        从最新轮次向前倒序装载，一旦整块加入会超预算，则终止并将更早轮次作为 evicted。
        """
        active_chunks_rev: List[TurnChunk] = []
        evicted_chunks: List[TurnChunk] = []
        remaining = max(0, budget_tokens)

        # 倒序遍历（从最新已完成轮次往最早轮次）
        for chunk in reversed(completed_turns):
            chunk_tokens = chunk.estimate_tokens(self.token_counter)
            if chunk_tokens <= remaining:
                active_chunks_rev.append(chunk)
                remaining -= chunk_tokens
            else:
                evicted_chunks.append(chunk)

        # 还原正序
        active_chunks = list(reversed(active_chunks_rev))
        # evicted_chunks 按照时间正序排列方便摘要阅读
        evicted_chunks = list(reversed(evicted_chunks))

        return active_chunks, evicted_chunks
