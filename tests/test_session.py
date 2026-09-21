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


    def test_rollback_disk_restoration_alignment(self):
        """验证点: 回滚操作落盘后，新建实例 restore_from_disk 时能够对齐回滚，工作记忆精准回退至前一轮"""
        mgr = ContextManager("test_rollback_alignment", budget_ledger=self.ledger)
        if mgr.history_file.exists():
            import os
            os.remove(mgr.history_file)

        # 第 1 轮: 修改 file_a.py
        mgr.start_new_turn("任务 1: 修改 file_a.py")
        mgr.working_memory.update_from_tool("write_file", {"file_path": "file_a.py"}, "ok")
        mgr.add_assistant_message("已完成 file_a.py 修改")
        mgr.finish_current_turn()

        # 第 2 轮: 修改 file_b.py
        mgr.start_new_turn("任务 2: 修改 file_b.py")
        mgr.working_memory.update_from_tool("write_file", {"file_path": "file_b.py"}, "ok")
        mgr.add_assistant_message("已完成 file_b.py 修改")
        mgr.finish_current_turn()

        self.assertIn("file_b.py", mgr.working_memory.modified_files)

        # 执行回滚第 2 轮
        success = mgr.rollback_last_turn()
        self.assertTrue(success)
        self.assertNotIn("file_b.py", mgr.working_memory.modified_files)
        self.assertIn("file_a.py", mgr.working_memory.modified_files)

        # 新实例从磁盘还原
        restored = ContextManager("test_rollback_alignment", budget_ledger=self.ledger)
        has_restored = restored.restore_from_disk()
        self.assertTrue(has_restored)

        # 核心断言: 还原后的实例中，已被回滚的轮次与工作记忆绝不能复活！
        self.assertEqual(len(restored.completed_turns), 1)
        self.assertEqual(restored.turn_count, 1)
        self.assertIn("file_a.py", restored.working_memory.modified_files)
        self.assertNotIn("file_b.py", restored.working_memory.modified_files, "已被回滚的轮次修改记录绝不能在 restore 后被恢复！")

        if mgr.history_file.exists():
            import os
            os.remove(mgr.history_file)


    def test_restore_from_disk_rebuilds_snapshot_stack_for_undo(self):
        """验证点: restore_from_disk 完整重建快照栈，恢复后连续执行多次回滚工作记忆均能精准退栈"""
        session_id = "test_multi_undo_after_restore"
        mgr = ContextManager(session_id, budget_ledger=self.ledger)
        if mgr.history_file.exists():
            import os
            os.remove(mgr.history_file)

        # 构造 3 个轮次，每轮修改不同文件
        for i in range(1, 4):
            mgr.start_new_turn(f"任务 {i}")
            mgr.working_memory.update_from_tool("write_file", {"file_path": f"file_{i}.py"}, "ok")
            mgr.add_assistant_message(f"完成任务 {i}")
            mgr.finish_current_turn()

        # 新建实例执行 restore
        restored = ContextManager(session_id, budget_ledger=self.ledger)
        self.assertTrue(restored.restore_from_disk())
        self.assertEqual(len(restored._state_snapshots), 3, "恢复后快照栈必须对齐历史完成轮次数！")

        # 连续回滚第 3 轮
        self.assertTrue(restored.rollback_last_turn())
        self.assertEqual(restored.turn_count, 2)
        self.assertNotIn("file_3.py", restored.working_memory.modified_files)
        self.assertIn("file_2.py", restored.working_memory.modified_files)

        # 再次回滚第 2 轮
        self.assertTrue(restored.rollback_last_turn())
        self.assertEqual(restored.turn_count, 1)
        self.assertNotIn("file_2.py", restored.working_memory.modified_files)
        self.assertIn("file_1.py", restored.working_memory.modified_files)

        if mgr.history_file.exists():
            import os
            os.remove(mgr.history_file)

    def test_init_turn_counter_resets_on_session_cleared(self):
        """验证点: 日志中存在 session_cleared 标记时，新会话 turn_count 正确归零从 1 开始自增"""
        session_id = "test_clear_reset_counter"
        mgr = ContextManager(session_id, budget_ledger=self.ledger)
        if mgr.history_file.exists():
            import os
            os.remove(mgr.history_file)

        # 运行两轮
        for i in range(1, 3):
            mgr.start_new_turn(f"旧任务 {i}")
            mgr.add_assistant_message(f"旧回复 {i}")
            mgr.finish_current_turn()

        # 用户清空会话
        mgr.clear()

        # 新实例探测历史 ID
        new_mgr = ContextManager(session_id, budget_ledger=self.ledger)
        self.assertEqual(new_mgr.turn_count, 0, "会话清空后，新建实例初始化计数必须归零！")

        # 开启新轮次必须是第 1 轮
        new_mgr.start_new_turn("新提问")
        self.assertEqual(new_mgr.turn_count, 1, "清空后的首次提问必须从 turn_id=1 重新开始！")

        if mgr.history_file.exists():
            import os
            os.remove(mgr.history_file)

if __name__ == "__main__":
    unittest.main()
