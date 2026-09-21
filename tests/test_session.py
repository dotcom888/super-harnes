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

        t1 = TurnChunk(1)
        t1.add_message({"role": "user", "content": "x" * 25})

        t2 = TurnChunk(2)
        t2.add_message({"role": "user", "content": "y" * 115})

        t3 = TurnChunk(3)
        t3.add_message({"role": "user", "content": "z" * 25})

        active, evicted = window.split_by_budget([t1, t2, t3], budget_tokens=80)

        active_ids = [c.turn_id for c in active]
        evicted_ids = [c.turn_id for c in evicted]

        self.assertEqual(active_ids, [3], "活跃轮次必须仅保留最近且连续的轮次")
        self.assertEqual(evicted_ids, [1, 2], "被淘汰轮次必须包含所有更早轮次，且保持时间正序")

    def test_turn_chunk_atomic_pairing_and_sanitization(self):
        """验证原子轮次双向成对清洗（孤立 tool 与未闭合 calls 同时清洗）"""
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
        # 包含一个合法结果和一个孤立结果
        chunk.add_message({"role": "tool", "tool_call_id": "call_1", "content": "文件内容"})
        chunk.add_message({"role": "tool", "tool_call_id": "call_ghost", "content": "幽灵结果"})

        self.assertFalse(chunk.is_paired_and_complete())

        # 执行双向清洗
        chunk.sanitize_unpaired_calls()
        self.assertTrue(chunk.is_paired_and_complete())
        
        # 验证孤立结果已被清理
        self.assertNotIn("call_ghost", chunk.get_tool_result_ids())
        self.assertIn("call_1", chunk.get_tool_result_ids())

    def test_full_disk_persistence_with_summary_and_wm_restore(self):
        """核心验证：落盘恢复必须完整还原 summary_state 和 working_memory"""
        self.manager.working_memory.update_goal("修复除零缺陷", is_manual=True)
        self.manager.working_memory.update_from_tool("read_file", {"file_path": "tools/calc.py"}, "code")
        self.manager.summarizer.state.summary_text = "早期已排查了 tools/calc.py"
        self.manager.summarizer.state.start_turn_id = 1
        self.manager.summarizer.state.end_turn_id = 2
        self.manager.summarizer.state.covered_through_turn_id = 2

        self.manager.start_new_turn("轮次 1 提问")
        self.manager.add_assistant_message("轮次 1 回答")
        self.manager.finish_current_turn()

        self.assertTrue(self.manager.history_file.exists())

        restored_manager = ContextManager(
            session_id=self.session_id,
            budget_ledger=self.ledger,
            token_counter=self.counter
        )
        success = restored_manager.restore_from_disk()
        self.assertTrue(success)
        self.assertEqual(restored_manager.turn_count, 1)

        self.assertEqual(restored_manager.working_memory.current_goal, "修复除零缺陷")
        self.assertIn("tools/calc.py", restored_manager.working_memory.inspected_files)

        self.assertTrue(restored_manager.summarizer.state.has_summary())
        self.assertEqual(restored_manager.summarizer.state.summary_text, "早期已排查了 tools/calc.py")
        self.assertEqual(restored_manager.summarizer.state.covered_through_turn_id, 2)

    def test_disk_restore_isolates_uncompleted_turns(self):
        """核心验证：进程崩溃遗留的未完成轮次，恢复时不进入 completed_turns"""
        self.manager.start_new_turn("轮次 1 正常完成")
        self.manager.add_assistant_message("轮次 1 正常回答")
        self.manager.finish_current_turn()

        self.manager.start_new_turn("轮次 2 中断提问")
        self.manager.add_assistant_message("轮次 2 中断回答")

        restored = ContextManager(
            session_id=self.session_id,
            budget_ledger=self.ledger,
            token_counter=self.counter
        )
        restored.restore_from_disk()

        self.assertEqual(len(restored.completed_turns), 1)
        self.assertEqual(restored.completed_turns[0].messages[0]["content"], "轮次 1 正常完成")

    def test_hard_gatekeeper_enforces_output_reserve(self):
        """核心验证：最终硬门禁确保 Context 总 Token 绝对不侵占 output_reserve"""
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

    def test_all_system_messages_at_head_for_api_compatibility(self):
        """验证所有 System 角色消息必须全部位于头部，杜绝在历史交互中间插入 system 触发 400 错误"""
        self.manager.summarizer.state.summary_text = "这是稳定的早期排查纪要"
        self.manager.summarizer.state.start_turn_id = 1
        self.manager.summarizer.state.end_turn_id = 1

        self.manager.start_new_turn("历史第 1 轮")
        self.manager.add_assistant_message("历史回答 1")
        self.manager.finish_current_turn()

        self.manager.start_new_turn("当前轮提问")
        self.manager.working_memory.update_goal("变更目标 A")

        msgs, _ = self.manager.build_context_with_watermark("Immutable Base System")

        # 验证前缀中的 system 角色消息连续且在历史之前
        seen_non_system = False
        for m in msgs:
            role = m.get("role")
            if role == "system":
                self.assertFalse(seen_non_system, "System 消息绝对不允许出现在 user/assistant/tool 消息之后！")
            else:
                seen_non_system = True

if __name__ == "__main__":
    unittest.main()
