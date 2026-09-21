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
        成对闭合校验：
        检查所有由 assistant 发起的 tool_calls 是否均有对应的 tool 结果回填，杜绝孤立调用。
        """
        calls = self.get_tool_call_ids()
        results = self.get_tool_result_ids()
        return calls == results

    def sanitize_unpaired_calls(self):
        """
        若由于异常中断导致存在未闭合的 tool_calls，进行安全清理，
        避免非法孤立消息送入大模型 API 触发 400 校验异常。
        """
        calls = self.get_tool_call_ids()
        results = self.get_tool_result_ids()
        unpaired = calls - results
        if not unpaired:
            return

        for msg in self.messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                msg["tool_calls"] = [
                    tc for tc in msg["tool_calls"]
                    if tc.get("id") not in unpaired
                ]
                if not msg["tool_calls"]:
                    del msg["tool_calls"]

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
        关键保障（修复穿孔 Bug）：
        一旦某一轮次整块加入会导致超出预算，立即终止装载，
        该轮次及其之前的所有更早轮次全部划入 evicted_chunks，确保 active_chunks 时间轴绝对连续！
        """
        if not completed_turns:
            return [], []

        active_chunks_rev: List[TurnChunk] = []
        cutoff_index = -1  # 记录从哪一个索引开始（倒序）无法装入
        remaining = max(0, budget_tokens)

        total_turns = len(completed_turns)
        # 从最新轮次倒序扫描到最早轮次
        for i in range(total_turns - 1, -1, -1):
            chunk = completed_turns[i]
            chunk_tokens = chunk.estimate_tokens(self.token_counter)
            if chunk_tokens <= remaining:
                active_chunks_rev.append(chunk)
                remaining -= chunk_tokens
            else:
                # 关键修复：一旦放不下，立即截断！不再贪心往前搜索较小轮次，避免时间穿孔
                cutoff_index = i
                break

        if cutoff_index == -1:
            # 全部轮次都在预算内装下
            evicted_chunks = []
        else:
            # 从 0 到 cutoff_index 的所有轮次均被淘汰，保持时间正序
            evicted_chunks = completed_turns[:cutoff_index + 1]

        # 还原 active_chunks 为时间正序
        active_chunks = list(reversed(active_chunks_rev))

        return active_chunks, evicted_chunks
