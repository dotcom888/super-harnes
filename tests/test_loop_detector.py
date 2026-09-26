import unittest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock

from core.loop_detector import LoopDetector, LoopState
from core.agent import ReActAgent
from context.manager import ContextManager
from context.budget import BudgetLedger

class TestLoopDetector(unittest.TestCase):
    """测试死循环与停滞监测引擎的核心算法 (模式 1、模式 2 与模式 3)"""

    def setUp(self):
        self.detector = LoopDetector(
            max_consecutive_duplicates=3,
            max_cycle_repetitions=3,
            max_repeated_errors=3
        )

    def test_mode_1_consecutive_duplicate_calls(self):
        """模式 1: 连续相同工具与参数 -> 第 2 次警告，第 3 次红牌强制收尾"""
        call = [{"function": {"name": "read_file", "arguments": json.dumps({"file_path": "main.py"})}}]

        # 第 1 次
        state_1 = self.detector.record_step(call)
        self.assertEqual(state_1, LoopState.NORMAL)

        # 第 2 次：触发 WARNING 黄牌
        state_2 = self.detector.record_step(call)
        self.assertEqual(state_2, LoopState.WARNING)
        self.assertIn("连续 2 步发起完全相同的工具调用", self.detector.diagnosis_reason)
        self.assertIn("[系统警示 - 停滞干预]", self.detector.get_warning_prompt_banner())

        # 第 3 次：触发 FORCE_WRAPUP 红牌
        state_3 = self.detector.record_step(call)
        self.assertEqual(state_3, LoopState.FORCE_WRAPUP)
        self.assertIn("连续 3 步发起完全相同的工具调用", self.detector.diagnosis_reason)
        self.assertIn("【注意: 为防止无限空转，工具调用权限已被强制关闭】", self.detector.get_wrapup_prompt_banner())

    def test_mode_2_oscillating_ping_pong_cycles(self):
        """模式 2: 工具交替振荡死循环 (Period = 2) -> 重复 2 次警告，重复 3 次红牌"""
        call_a = [{"function": {"name": "read_file", "arguments": json.dumps({"file_path": "a.py"})}}]
        call_b = [{"function": {"name": "read_file", "arguments": json.dumps({"file_path": "b.py"})}}]

        # 周期 1: A -> B
        self.assertEqual(self.detector.record_step(call_a), LoopState.NORMAL)
        self.assertEqual(self.detector.record_step(call_b), LoopState.NORMAL)

        # 周期 2: A -> B (振荡重复 2 次 -> WARNING)
        self.assertEqual(self.detector.record_step(call_a), LoopState.NORMAL)
        state_cycle_2 = self.detector.record_step(call_b)
        self.assertEqual(state_cycle_2, LoopState.WARNING)
        self.assertIn("反复振荡倾向", self.detector.diagnosis_reason)

        # 周期 3: A -> B (振荡重复 3 次 -> FORCE_WRAPUP)
        # 第 5 步: [A, B, A, B, A] 中 [B, A] 已重复 2 次 -> WARNING
        self.assertEqual(self.detector.record_step(call_a), LoopState.WARNING)
        # 第 6 步: [A, B, A, B, A, B] 中 [A, B] 完整重复 3 次 -> FORCE_WRAPUP
        state_cycle_3 = self.detector.record_step(call_b)
        self.assertEqual(state_cycle_3, LoopState.FORCE_WRAPUP)
        self.assertIn("振荡死循环", self.detector.diagnosis_reason)

    def test_mode_3_consecutive_identical_errors(self):
        """模式 3: 连续相同报错停滞 -> 连续 3 次相同错误触发 FORCE_WRAPUP"""
        call = [{"function": {"name": "apply_patch", "arguments": json.dumps({"file_path": "foo.py"})}}]
        res_fail = [{"content": "【补丁失败】：在文件中未找到指定的 SEARCH 代码块！"}]

        # 第 1 次报错
        self.assertEqual(self.detector.record_step(call, res_fail), LoopState.NORMAL)

        # 第 2 次相同报错
        call_diff_arg = [{"function": {"name": "apply_patch", "arguments": json.dumps({"file_path": "foo.py", "attempt": 2})}}]
        self.assertEqual(self.detector.record_step(call_diff_arg, res_fail), LoopState.NORMAL)

        # 第 3 次相同报错 -> 触发 FORCE_WRAPUP
        call_diff_arg_3 = [{"function": {"name": "apply_patch", "arguments": json.dumps({"file_path": "foo.py", "attempt": 3})}}]
        state_err = self.detector.record_step(call_diff_arg_3, res_fail)
        self.assertEqual(state_err, LoopState.FORCE_WRAPUP)
        self.assertIn("连续 3 步遭遇完全相同的失败报错", self.detector.diagnosis_reason)


class TestUnboundedReActExecution(unittest.TestCase):
    """测试 ReActAgent 无上限自主执行模式与死循环安全熔断联动"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_unbounded_")
        self.mgr = ContextManager("test_unbounded_session", base_dir=Path(self.temp_dir))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_unbounded_mode_natural_exit_when_no_tool_calls(self):
        """验证无上限模式 (max_steps=0): 大模型完成排查不调用工具时，自然结束循环"""
        agent = ReActAgent.__new__(ReActAgent)
        agent.system_prompt = "You are a coding assistant."
        agent.max_steps = 0  # 无上限模式
        agent.model = "mock-model"
        agent.context_manager = self.mgr
        agent.loop_detector = LoopDetector()
        agent.executor = MagicMock()
        agent.executor.registry.get_schemas.return_value = [{"type": "function", "function": {"name": "read_file"}}]

        # 模拟 3 步执行：Step 1 tool, Step 2 tool, Step 3 纯文本答复完成
        call_1 = MagicMock(id="c1", type="function", function=MagicMock(name="read_file", arguments='{"file_path":"a.py"}'))
        resp_1 = MagicMock(choices=[MagicMock(message=MagicMock(content="Read A", tool_calls=[call_1]))], usage=None)

        call_2 = MagicMock(id="c2", type="function", function=MagicMock(name="read_file", arguments='{"file_path":"b.py"}'))
        resp_2 = MagicMock(choices=[MagicMock(message=MagicMock(content="Read B", tool_calls=[call_2]))], usage=None)

        resp_3 = MagicMock(choices=[MagicMock(message=MagicMock(content="任务已彻底达成，无需继续调用工具。", tool_calls=None))], usage=None)

        agent.client = MagicMock()
        agent.client.chat.completions.create.side_effect = [resp_1, resp_2, resp_3]
        agent.executor.execute_tool_calls.return_value = [{"tool_call_id": "c", "content": "file ok"}]

        final_ans = agent.run("请排查项目", verbose=False)
        self.assertEqual(final_ans, "任务已彻底达成，无需继续调用工具。")
        self.assertEqual(agent.client.chat.completions.create.call_count, 3)

    def test_unbounded_mode_force_wrapup_on_dead_loop(self):
        """验证无上限模式下，大模型陷入复读死循环时，系统自动拦截并在红牌后关闭工具安全收尾"""
        agent = ReActAgent.__new__(ReActAgent)
        agent.system_prompt = "You are a coding assistant."
        agent.max_steps = 0  # 无上限模式
        agent.model = "mock-model"
        agent.context_manager = self.mgr
        agent.loop_detector = LoopDetector(max_consecutive_duplicates=3)
        agent.executor = MagicMock()
        agent.executor.registry.get_schemas.return_value = [{"type": "function", "function": {"name": "read_file"}}]

        # 连续 3 步发起完全相同的调用
        call_dup = MagicMock(id="c_dup", type="function", function=MagicMock(name="read_file", arguments='{"file_path":"same.py"}'))
        resp_tool = MagicMock(choices=[MagicMock(message=MagicMock(content="Repeating", tool_calls=[call_dup]))], usage=None)

        # 最终步（红牌触发后 tools=None），模型输出最终解释
        resp_wrapup = MagicMock(choices=[MagicMock(message=MagicMock(content="已停止排查并汇总已知结论。", tool_calls=None))], usage=None)

        # 序列: Step 1 (dup), Step 2 (dup), Step 3 (dup -> 触发 FORCE_WRAPUP), Step 4 (tools=None -> wrapup)
        agent.client = MagicMock()
        agent.client.chat.completions.create.side_effect = [resp_tool, resp_tool, resp_tool, resp_wrapup]
        agent.executor.execute_tool_calls.return_value = [{"tool_call_id": "c_dup", "content": "same content"}]

        final_ans = agent.run("请重复读取", verbose=False)
        self.assertEqual(final_ans, "已停止排查并汇总已知结论。")

        # 核心断言：在 Step 4 时，tools 参数必须被强制关闭为 None
        calls = agent.client.chat.completions.create.call_args_list
        self.assertEqual(len(calls), 4)
        self.assertIsNotNone(calls[2][1].get("tools"))
        self.assertIsNone(calls[3][1].get("tools"), "死循环红牌触发后，必须强制关闭工具参数！")

if __name__ == "__main__":
    unittest.main()
