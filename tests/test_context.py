# -*- coding: utf-8 -*-
import unittest
import os
from context import ContextManager, WatermarkZone

class TestContextWatermark(unittest.TestCase):
    def setUp(self):
        self.mgr = ContextManager("test_watermark_session", max_budget_tokens=100)
        self.mgr.clear()

    def tearDown(self):
        if self.mgr.history_file.exists():
            try:
                os.remove(self.mgr.history_file)
            except Exception:
                pass

    def test_green_zone_passthrough(self):
        """测试使用率 < 60%: 绿区全量直通，零裁剪、无摘要"""
        self.mgr.start_new_turn("短提问 1")
        self.mgr.add_assistant_message("短回答 1")
        self.mgr.finish_current_turn()

        self.mgr.start_new_turn("当前进行中短提问")
        messages, metrics = self.mgr.build_context_with_watermark("System base")

        self.assertEqual(metrics["zone"], WatermarkZone.GREEN)
        self.assertLess(metrics["raw_utilization"], 0.60)
        self.assertEqual(metrics["evicted_turns"], 0)
        self.assertFalse(metrics["has_summary"])

        user_texts = [m["content"] for m in messages if m["role"] == "user"]
        self.assertIn("短提问 1", user_texts)
        self.assertIn("当前进行中短提问", user_texts)

    def test_yellow_zone_sliding_window(self):
        """测试使用率 60% ~ 75%: 黄区正常滑动窗口淘汰，无摘要"""
        self.mgr.start_new_turn("早前轮次: 简单提问 1")
        self.mgr.add_assistant_message("回答: 快速诊断完成")
        self.mgr.finish_current_turn()

        self.mgr.start_new_turn("较新轮次: 简单提问 2")
        self.mgr.add_assistant_message("回答: 模块导入正常")
        self.mgr.finish_current_turn()

        self.mgr.start_new_turn("当前提问")
        messages, metrics = self.mgr.build_context_with_watermark("System base")

        self.assertEqual(metrics["zone"], WatermarkZone.YELLOW)
        self.assertGreaterEqual(metrics["raw_utilization"], 0.60)
        self.assertLess(metrics["raw_utilization"], 0.75)
        self.assertFalse(metrics["has_summary"])

    def test_red_zone_summary_compaction(self):
        """测试使用率 >= 75%: 红区触发 Summary Compaction 深度摘要压缩"""
        self.mgr.start_new_turn("排查历史 1: tools/calculator.py 存在除零错误 " + "x" * 70)
        self.mgr.add_assistant_message("确认了计算器错误 " + "y" * 70)
        self.mgr.finish_current_turn()

        self.mgr.start_new_turn("排查历史 2: tools/file_tools.py 读行范围溢出 " + "m" * 70)
        self.mgr.add_assistant_message("修复了读取行数限制 " + "n" * 70)
        self.mgr.finish_current_turn()

        self.mgr.start_new_turn("当前任务提问")
        messages, metrics = self.mgr.build_context_with_watermark("System base")

        self.assertEqual(metrics["zone"], WatermarkZone.RED)
        self.assertGreaterEqual(metrics["raw_utilization"], 0.75)
        self.assertTrue(metrics["has_summary"])
        self.assertIn("早前排查与修改历史纪要", messages[0]["content"])

if __name__ == "__main__":
    unittest.main()
