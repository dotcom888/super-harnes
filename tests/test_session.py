# -*- coding: utf-8 -*-
import unittest
import os
from session import Session, WorkingMemory, TurnChunk

class TestSafeSlidingWindow(unittest.TestCase):
    def setUp(self):
        self.session = Session("test_sliding_window", max_budget_tokens=300)
        self.session.clear()

    def tearDown(self):
        if self.session.history_file.exists():
            try:
                os.remove(self.session.history_file)
            except Exception:
                pass

    def test_principles_1_2_6_retention(self):
        """验证原则 1(System 保留)、原则 2(Working Memory 保留)、原则 6(当前轮不截断)"""
        self.session.working_memory.update_goal("排查计算器除零 Bug")
        self.session.working_memory.update_from_tool("read_file", {"file_path": "tools/calc.py"}, "code...")

        self.session.start_new_turn("当前用户的提问")
        self.session.add_assistant_message({
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}]
        })
        self.session.add_tool_results([{"tool_call_id": "call_1", "content": "行 1 到 50 内容"}])

        messages = self.session.build_messages("You are a helpful coding agent.")

        # 原则 1 & 2: System prompt 位于索引 0，且内含 Working Memory
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("You are a helpful coding agent.", messages[0]["content"])
        self.assertIn("排查计算器除零 Bug", messages[0]["content"])
        self.assertIn("tools/calc.py", messages[0]["content"])

        # 原则 6: 当前轮的所有消息完整无损
        roles = [m["role"] for m in messages[1:]]
        self.assertEqual(roles, ["user", "assistant", "tool"])

    def test_principles_3_4_5_reverse_scan_and_atomic_pairing(self):
        """验证原则 3(倒序扫描)、原则 4(超预算停止)、原则 5(tool_call与结果严格成对原子绑定)"""
        # 设定刚好能容纳 (System + 当前轮 + 历史第 2 轮) 但容不下第 1 轮的精确预算
        small_session = Session("test_small_budget", max_budget_tokens=85)
        
        # 构造历史第 1 轮（较旧的轮次）
        small_session.start_new_turn("历史第 1 轮：先读 readme")
        small_session.add_assistant_message("已阅读 readme 内容 " + "x" * 100)
        small_session.finish_current_turn()

        # 构造历史第 2 轮（较新的轮次，包含 tool 调用与结果对）
        small_session.start_new_turn("历史第 2 轮：执行工具排查")
        small_session.add_assistant_message({
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "call_history", "type": "function", "function": {"name": "run_shell", "arguments": "ls"}}]
        })
        small_session.add_tool_results([{"tool_call_id": "call_history", "content": "file1 file2"}])
        small_session.add_assistant_message("工具执行成功")
        small_session.finish_current_turn()

        # 构造当前正在执行的第 3 轮
        small_session.start_new_turn("当前第 3 轮：继续排查")

        messages = small_session.build_messages("System base")

        user_messages = [m["content"] for m in messages if m["role"] == "user"]
        # 原则 3 & 4: 较新的第 2 轮被放入，较旧的第 1 轮因超预算被安全停止装载
        self.assertNotIn("历史第 1 轮：先读 readme", user_messages)
        self.assertIn("历史第 2 轮：执行工具排查", user_messages)
        self.assertIn("当前第 3 轮：继续排查", user_messages)

        # 原则 5: 第 2 轮里的 tool_calls 和 tool 结果必须严格成对存在，绝不能只切入一半
        assistant_tools = [m for m in messages if m.get("tool_calls")]
        tool_results = [m for m in messages if m.get("role") == "tool"]
        self.assertEqual(len(assistant_tools), 1)
        self.assertEqual(len(tool_results), 1)
        self.assertEqual(assistant_tools[0]["tool_calls"][0]["id"], tool_results[0]["tool_call_id"])

        if small_session.history_file.exists():
            os.remove(small_session.history_file)

    def test_disk_persistence_and_restore(self):
        """验证磁盘 history/ 目录落盘与恢复功能"""
        persist_session = Session("test_disk_archive", max_budget_tokens=1000)
        persist_session.start_new_turn("落盘测试提问")
        persist_session.add_assistant_message("落盘测试回答")
        persist_session.finish_current_turn()

        # 验证文件已落盘
        self.assertTrue(persist_session.history_file.exists())

        # 新建一个实例并恢复
        new_session = Session("test_disk_archive", max_budget_tokens=1000)
        success = new_session.restore_from_disk()
        self.assertTrue(success)
        self.assertEqual(new_session.turn_count, 1)
        self.assertEqual(new_session.completed_turns[0].messages[0]["content"], "落盘测试提问")

        if persist_session.history_file.exists():
            os.remove(persist_session.history_file)

if __name__ == "__main__":
    unittest.main()
