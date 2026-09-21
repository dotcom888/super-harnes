# -*- coding: utf-8 -*-
import unittest
import os
import shutil
from typing import List, Dict, Any
from context import (
    ContextManager,
    WorkingMemory,
    TurnChunk,
    BudgetLedger,
    SlidingWindow,
    TokenCounter
)

class TestSafeSlidingWindowAndSession(unittest.TestCase):
    """验证安全滑动窗口核心机制、成对绑定、真实落盘恢复与硬预算门禁"""

    def setUp(self):
        self.session_id = "test_verified_session"
        # 设定可控账本：总预算 400，系统 50，工具 50，记忆 50，输出 100，历史预算 150
        self.ledger = BudgetLedger(
            total_budget=400,
            system_reserve=50,
            tools_reserve=50,
            memory_reserve=50,
            output_reserve=100,
            min_history_budget=50
        )
        self.counter = TokenCounter(char_per_token=1.0)
        self.manager = ContextManager(
            session_id=self.session_id,
            budget_ledger=self.ledger,
            token_counter=self.counter
        )
        self.manager.clear()

    def tearDown(self):
        if self.manager.history_file.exists():
            try:
                os.remove(self.manager.history_file)
            except Exception:
                pass

    def test_sliding_window_strict_continuity_no_perforation(self):
        """核心验证：彻底杜绝滑窗时间穿孔，确保 active_chunks 严格连续"""
        window = SlidingWindow(self.counter)

        # 轮次 1: 30 tokens
        t1 = TurnChunk(1)
        t1.add_message({"role": "user", "content": "x" * 25})

        # 轮次 2: 120 tokens (中间大轮次)
        t2 = TurnChunk(2)
        t2.add_message({"role": "user", "content": "y" * 115})

        # 轮次 3: 30 tokens (较新轮次)
        t3 = TurnChunk(3)
        t3.add_message({"role": "user", "content": "z" * 25})

        # 历史预算只有 80 tokens：
        # 倒序装入 t3 (30, 余 50) -> 检查 t2 (120 > 50) -> 必须立即截断！
        # 绝不能越过 t2 去装 t1，否则将产生 [t1, t3] 的穿孔！
        active, evicted = window.split_by_budget([t1, t2, t3], budget_tokens=80)

        active_ids = [c.turn_id for c in active]
        evicted_ids = [c.turn_id for c in evicted]

        self.assertEqual(active_ids, [3], "活跃轮次必须仅保留最近且连续的轮次")
        self.assertEqual(evicted_ids, [1, 2], "被淘汰轮次必须包含所有更早轮次，且保持时间正序")

    def test_turn_chunk_atomic_pairing_and_sanitization(self):
        """验证原子轮次成对绑定校验与未闭合调用安全清洗"""
        chunk = TurnChunk(1)
        chunk.add_message({"role": "user", "content": "执行排查"})
        chunk.add_message({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "read_file", "arguments": "{}"}},
                {"id": "call_2", "type": "function", "function": {"name": "run_shell", "arguments": "{}"}}
            ]
        })
        # 仅回填 call_1，call_2 未闭合
        chunk.add_message({"role": "tool", "tool_call_id": "call_1", "content": "文件内容"})

        self.assertFalse(chunk.is_paired_and_complete(), "存在未闭合的 tool 调用时应返回 False")

        # 执行清洗
        chunk.sanitize_unpaired_calls()
        self.assertTrue(chunk.is_paired_and_complete(), "清洗后所有 tool_calls 必须与 tool 结果成对匹配")
        assistant_msg = chunk.messages[1]
        self.assertEqual(len(assistant_msg["tool_calls"]), 1)
        self.assertEqual(assistant_msg["tool_calls"][0]["id"], "call_1")

    def test_full_disk_persistence_with_summary_and_wm_restore(self):
        """核心验证：落盘恢复必须完整还原 summary_state 和 working_memory"""
        # 设置状态
        self.manager.working_memory.update_goal("修复除零缺陷")
        self.manager.working_memory.update_from_tool("read_file", {"file_path": "tools/calc.py"}, "code")
        self.manager.summarizer.state.summary_text = "早期已排查了 tools/calc.py"
        self.manager.summarizer.state.start_turn_id = 1
        self.manager.summarizer.state.end_turn_id = 2
        self.manager.summarizer.state.covered_through_turn_id = 2

        # 完成第 1 轮
        self.manager.start_new_turn("轮次 1 提问")
        self.manager.add_assistant_message("轮次 1 回答")
        self.manager.finish_current_turn()

        self.assertTrue(self.manager.history_file.exists())

        # 新建实例从磁盘恢复
        restored_manager = ContextManager(
            session_id=self.session_id,
            budget_ledger=self.ledger,
            token_counter=self.counter
        )
        success = restored_manager.restore_from_disk()
        self.assertTrue(success)
        self.assertEqual(restored_manager.turn_count, 1)

        # 检查 WorkingMemory 恢复
        self.assertEqual(restored_manager.working_memory.current_goal, "修复除零缺陷")
        self.assertIn("tools/calc.py", restored_manager.working_memory.inspected_files)

        # 检查 SummaryState 恢复（曾是重大遗漏）
        self.assertTrue(restored_manager.summarizer.state.has_summary())
        self.assertEqual(restored_manager.summarizer.state.summary_text, "早期已排查了 tools/calc.py")
        self.assertEqual(restored_manager.summarizer.state.covered_through_turn_id, 2)

    def test_disk_restore_isolates_uncompleted_turns(self):
        """核心验证：进程崩溃遗留的未完成轮次，恢复时不进入 completed_turns"""
        # 轮次 1: 正常完成
        self.manager.start_new_turn("轮次 1 正常完成")
        self.manager.add_assistant_message("轮次 1 正常回答")
        self.manager.finish_current_turn()

        # 轮次 2: 正在进行途中发生崩溃（未调用 finish_current_turn，缺少 turn_finished 记录）
        self.manager.start_new_turn("轮次 2 中断提问")
        self.manager.add_assistant_message("轮次 2 中断回答")

        # 恢复
        restored = ContextManager(
            session_id=self.session_id,
            budget_ledger=self.ledger,
            token_counter=self.counter
        )
        restored.restore_from_disk()

        # 仅轮次 1 被视为已完成历史，轮次 2 绝不污染 completed_turns
        self.assertEqual(len(restored.completed_turns), 1)
        self.assertEqual(restored.completed_turns[0].messages[0]["content"], "轮次 1 正常完成")

    def test_hard_gatekeeper_enforces_output_reserve(self):
        """核心验证：最终硬门禁确保 Context 总 Token 绝对不侵占 output_reserve"""
        # 总预算 250，输出预留 100，实际可用上限 150
        tiny_ledger = BudgetLedger(
            total_budget=250,
            system_reserve=20,
            tools_reserve=20,
            memory_reserve=20,
            output_reserve=100,
            min_history_budget=20
        )
        mgr = ContextManager(
            session_id="test_tiny_gate",
            budget_ledger=tiny_ledger,
            token_counter=self.counter
        )

        for i in range(1, 4):
            mgr.start_new_turn(f"长轮次提问 #{i} " + "w" * 40)
            mgr.add_assistant_message(f"长轮次回答 #{i} " + "w" * 40)
            mgr.finish_current_turn()

        # 当前轮次
        mgr.start_new_turn("当前提问")

        messages, metrics = mgr.build_context_with_watermark("Base System Prompt")

        max_allowed = tiny_ledger.total_budget - tiny_ledger.output_reserve
        actual_tokens = mgr.token_counter.count_messages(messages)
        self.assertLessEqual(
            actual_tokens,
            max_allowed,
            f"最终装配的总 Tokens ({actual_tokens}) 绝对不能超过允许上限 ({max_allowed})"
        )

        if mgr.history_file.exists():
            os.remove(mgr.history_file)

    def test_prompt_cache_prefix_stability(self):
        """验证 Prompt 缓存前缀友好结构：Base System 和 Summary 位于前缀"""
        self.manager.summarizer.state.summary_text = "这是稳定的早期排查纪要"
        self.manager.summarizer.state.start_turn_id = 1
        self.manager.summarizer.state.end_turn_id = 1

        self.manager.start_new_turn("历史第 1 轮")
        self.manager.add_assistant_message("历史回答 1")
        self.manager.finish_current_turn()

        # 当前轮更新 Working Memory
        self.manager.start_new_turn("当前轮提问")
        self.manager.working_memory.update_goal("变更目标 A")

        msgs_a, _ = self.manager.build_context_with_watermark("Immutable Base System")

        # 索引 0 必须是 Base System
        self.assertEqual(msgs_a[0]["role"], "system")
        self.assertEqual(msgs_a[0]["content"], "Immutable Base System")

        # 索引 1 必须是 Summary
        self.assertEqual(msgs_a[1]["role"], "system")
        self.assertIn("历史排查与修改纪要", msgs_a[1]["content"])

        # 紧接着必须是历史轮次消息，而不是频繁变动的 WorkingMemory
        self.assertEqual(msgs_a[2]["role"], "user")
        self.assertEqual(msgs_a[2]["content"], "历史第 1 轮")

if __name__ == "__main__":
    unittest.main()
