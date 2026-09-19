# -*- coding: utf-8 -*-
import unittest
from session import Session, WorkingMemory

class TestSessionAndWorkingMemory(unittest.TestCase):
    def setUp(self):
        self.session = Session("test_session")

    def test_multi_turn_persistence(self):
        # 第 1 轮
        self.session.add_user_message("请帮我查看 requirements.txt")
        self.session.add_assistant_message("正在为您读取...")
        self.assertEqual(self.session.turn_count, 1)
        self.assertEqual(len(self.session.messages), 2)

        # 第 2 轮
        self.session.add_user_message("里面有 pytest 吗？")
        self.session.add_assistant_message("没有找到 pytest。")
        self.assertEqual(self.session.turn_count, 2)
        self.assertEqual(len(self.session.messages), 4)

    def test_working_memory_update_from_tools(self):
        wm = self.session.working_memory

        # 1. 模拟 read_file
        wm.update_from_tool("read_file", {"file_path": "tools/calculator.py", "start_line": 1, "max_lines": 50}, "code...")
        self.assertIn("tools/calculator.py", wm.inspected_files)

        # 2. 模拟 apply_patch
        patch = """*** Update File: tools/calculator.py
<<<<<<< SEARCH
old
=======
new
>>>>>>> REPLACE"""
        wm.update_from_tool("apply_patch", {"patch_content": patch}, "【补丁成功】")
        self.assertIn("tools/calculator.py", wm.modified_files)

        # 3. 模拟 run_shell
        wm.update_from_tool("run_shell", {"command": "python -m unittest"}, "【执行状态: 成功】\nOK")
        self.assertIn("python -m unittest", wm.last_test_status)

        # 校验上下文注入
        ctx = wm.format_prompt_context()
        self.assertIn("已排查代码", ctx)
        self.assertIn("已修改文件", ctx)
        self.assertIn("最新验证状态", ctx)

    def test_compact_history_preserves_protocol(self):
        # 构造第 1 轮：包含超大输出的 tool
        self.session.add_user_message("查询大日志")
        self.session.add_assistant_message({
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "call_123", "type": "function", "function": {"name": "run_shell", "arguments": "{}"}}]
        })
        long_output = "Line info " * 200  # 超过 500 字符
        self.session.add_tool_results([{"tool_call_id": "call_123", "content": long_output}])
        self.session.add_assistant_message("日志分析完成。")

        # 构造第 2 轮
        self.session.add_user_message("继续分析")
        
        # 触发压缩
        self.session.compact_history(max_observation_chars=100)

        # 验证第 1 轮的 tool 消息被安全折叠，但 tool_call_id 完好无损
        tool_msg = self.session.messages[2]
        self.assertEqual(tool_msg["role"], "tool")
        self.assertEqual(tool_msg["tool_call_id"], "call_123")
        self.assertIn("历史详细日志已折叠", tool_msg["content"])
        self.assertLess(len(tool_msg["content"]), len(long_output))

    def test_rollback(self):
        self.session.add_user_message("第一轮输入")
        self.session.add_assistant_message("第一轮回答")
        self.session.add_user_message("第二轮错误输入")
        self.session.add_assistant_message("第二轮回答")

        success = self.session.rollback_last_turn()
        self.assertTrue(success)
        self.assertEqual(len(self.session.messages), 2)
        self.assertEqual(self.session.messages[-1]["content"], "第一轮回答")

if __name__ == "__main__":
    unittest.main()
