# -*- coding: utf-8 -*-
import unittest
import os
from context import ContextManager, WatermarkZone, BudgetLedger, TokenCounter

class TestContextEnhancements(unittest.TestCase):
    def setUp(self):
        # 设定一个小型可控账本：总预算 300，各预留分账
        self.ledger = BudgetLedger(
            total_budget=300,
            system_reserve=30,
            tools_reserve=30,
            memory_reserve=30,
            output_reserve=60
        )
        self.mgr = ContextManager("test_enhanced_session", budget_ledger=self.ledger)
        self.mgr.clear()

    def tearDown(self):
        if self.mgr.history_file.exists():
            try:
                os.remove(self.mgr.history_file)
            except Exception:
                pass

    def test_point_1_system_prompt_immutability(self):
        """验证点 1: System Prompt 保持只读与不可变，动态内容作为独立系统注记装配"""
        original_prompt = "You are a pure coding agent."
        self.mgr.working_memory.update_goal("排查除零 Bug")

        # 人为注入一段摘要
        self.mgr.summarizer.state.summary_text = "之前已修复了 tools/calc.py"
        self.mgr.summarizer.state.start_turn_id = 1
        self.mgr.summarizer.state.end_turn_id = 3

        messages, _ = self.mgr.build_context_with_watermark(original_prompt)

        # 原始 System Prompt 绝未被修改
        self.assertEqual(original_prompt, "You are a pure coding agent.")
        self.assertEqual(messages[0]["content"], original_prompt)

        # 摘要与 Working Memory 作为独立的系统块注记装配，保持 Prompt Cache
        summary_msgs = [m for m in messages if "历史排查与修改纪要" in m.get("content", "")]
        wm_msgs = [m for m in messages if "工作区感知状态" in m.get("content", "")]
        self.assertEqual(len(summary_msgs), 1)
        self.assertEqual(len(wm_msgs), 1)

    def test_point_2_budget_ledger_allocation(self):
        """验证点 2: 24,000 硬预算分账账本正确运作，滑窗只占用 history 独立额度"""
        ledger = BudgetLedger(
            total_budget=24000,
            system_reserve=2000,
            tools_reserve=2000,
            memory_reserve=2000,
            output_reserve=3000
        )
        # 15000 = 24000 - (2000 + 2000 + 2000 + 3000)
        self.assertEqual(ledger.history_budget, 15000)
        self.assertEqual(ledger.output_reserve, 3000)

    def test_point_3_summary_range_tracking(self):
        """验证点 3: Summary 必须精准记录总结了哪一段历史区间 (Range Tracking)"""
        for i in range(1, 4):
            self.mgr.start_new_turn(f"轮次 #{i} 提问 " + "x" * 20)
            self.mgr.add_assistant_message(f"轮次 #{i} 回答 " + "y" * 20)
            self.mgr.finish_current_turn()

        # 执行一次摘要
        self.mgr.summarizer.summarize(self.mgr.completed_turns, current_turn_id=3)

        state = self.mgr.summarizer.state
        self.assertEqual(state.start_turn_id, 1)
        self.assertEqual(state.end_turn_id, 3)
        self.assertEqual(state.covered_through_turn_id, 3)
        self.assertIn("已覆盖轮次 #1 ~ #3", state.get_range_header())

    def test_point_4_anti_jitter_debounce(self):
        """验证点 4: 防摘要抖动护栏 (Debounce Guard) 避免频繁调用摘要"""
        summarizer = self.mgr.summarizer
        summarizer.min_turn_delta = 3
        summarizer.min_token_delta = 500

        # 仅淘汰 1 轮（未达到 3 轮门槛）
        chunk1 = self.mgr.completed_turns[:1] if self.mgr.completed_turns else []
        self.assertFalse(summarizer.should_summarize(chunk1, current_turn_id=4))

    def test_point_5_budget_ledger_validation_and_dynamic_recalc(self):
        """验证点 5: 账本参数校验、超支判定与实际用量动态重算"""
        # 非法参数（负数或预留超过总预算）必须抛出 ValueError
        with self.assertRaises(ValueError):
            BudgetLedger(total_budget=1000, system_reserve=-100)

        with self.assertRaises(ValueError):
            BudgetLedger(
                total_budget=1000,
                system_reserve=300,
                tools_reserve=300,
                memory_reserve=300,
                output_reserve=300  # 和为 1200 > 1000
            )

        ledger = BudgetLedger(total_budget=10000, output_reserve=2000)
        # 动态根据实际 tools (例如 3500 tokens) 和实际 system (例如 800 tokens) 重算
        new_history = ledger.recalculate_history_budget(
            actual_system_tokens=800,
            actual_tools_tokens=3500,
            actual_memory_tokens=1000
        )
        # 10000 - (800 + 3500 + 1000 + 2000) = 2700
        self.assertEqual(new_history, 2700)
        self.assertEqual(ledger.get_remaining_budget(8000), 2000)
        self.assertTrue(ledger.is_over_budget(10001))
        self.assertFalse(ledger.is_over_budget(9999))

    def test_point_6_token_counter_precision_and_structures(self):
        """验证点 6: TokenCounter 中英文分级加权与 OpenAI 消息结构开销"""
        counter = TokenCounter()
        # 中文计费高于 2.8 字符/token
        text_cn = "排查计算器除零异常并更新单元测试"  # 16 个汉字
        tokens_cn = counter.count_text(text_cn)
        self.assertGreaterEqual(tokens_cn, 16, "每个汉字通常不应低于 1 个 Token")

        # 包含 tool_calls 与结构开销
        msg = {
            "role": "assistant",
            "content": "正在调用工具",
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "apply_patch",
                        "arguments": '{"patch_content": "*** Update File: main.py"}'
                    }
                }
            ]
        }
        tokens_msg = counter.count_message(msg)
        self.assertGreater(tokens_msg, 20)

if __name__ == "__main__":
    unittest.main()
