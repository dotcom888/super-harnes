# -*- coding: utf-8 -*-
import unittest
import os
from pathlib import Path
from context import ContextManager, WatermarkZone, BudgetLedger, TokenCounter, TurnChunk

class TestContextEnhancements(unittest.TestCase):
    def setUp(self):
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

        self.mgr.summarizer.state.summary_text = "之前已修复了 tools/calc.py"
        self.mgr.summarizer.state.start_turn_id = 1
        self.mgr.summarizer.state.end_turn_id = 3

        messages, _ = self.mgr.build_context_with_watermark(original_prompt)

        self.assertEqual(original_prompt, "You are a pure coding agent.")
        self.assertEqual(messages[0]["content"], original_prompt)

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
        self.assertEqual(ledger.history_budget, 15000)
        self.assertEqual(ledger.output_reserve, 3000)

    def test_point_3_summary_range_tracking(self):
        """验证点 3: Summary 必须精准记录总结了哪一段历史区间 (Range Tracking)"""
        for i in range(1, 4):
            self.mgr.start_new_turn(f"轮次 #{i} 提问 " + "x" * 20)
            self.mgr.add_assistant_message(f"轮次 #{i} 回答 " + "y" * 20)
            self.mgr.finish_current_turn()

        self.mgr.summarizer.summarize(self.mgr.completed_turns, current_turn_id=3)

        state = self.mgr.summarizer.state
        self.assertEqual(state.start_turn_id, 1)
        self.assertEqual(state.end_turn_id, 3)
        self.assertEqual(state.covered_through_turn_id, 3)
        self.assertIn("已覆盖轮次 #1 ~ #3", state.get_range_header())

    def test_point_4_anti_jitter_debounce(self):
        """验证点 4: 防摘要抖动护栏 (Debounce Guard) 避免频繁调用大模型摘要"""
        summarizer = self.mgr.summarizer
        summarizer.min_turn_delta = 3
        summarizer.min_token_delta = 500

        chunk1 = self.mgr.completed_turns[:1] if self.mgr.completed_turns else []
        self.assertFalse(summarizer.should_summarize(chunk1, current_turn_id=4))

    def test_point_5_budget_ledger_validation_and_dynamic_recalc(self):
        """验证点 5: 账本参数校验、超支判定与实际用量动态重算"""
        with self.assertRaises(ValueError):
            BudgetLedger(total_budget=1000, system_reserve=-100)

        with self.assertRaises(ValueError):
            BudgetLedger(
                total_budget=1000,
                system_reserve=300,
                tools_reserve=300,
                memory_reserve=300,
                output_reserve=300
            )

        ledger = BudgetLedger(total_budget=10000, output_reserve=2000)
        new_history = ledger.recalculate_history_budget(
            actual_system_tokens=800,
            actual_tools_tokens=3500,
            actual_memory_tokens=1000
        )
        self.assertEqual(new_history, 2700)
        self.assertEqual(ledger.get_remaining_budget(8000), 2000)
        self.assertTrue(ledger.is_over_budget(10001))
        self.assertFalse(ledger.is_over_budget(9999))

    def test_point_6_token_counter_precision_and_structures(self):
        """验证点 6: TokenCounter 中英文分级加权与 OpenAI 消息结构开销"""
        counter = TokenCounter()
        text_cn = "排查计算器除零异常并更新单元测试"
        tokens_cn = counter.count_text(text_cn)
        self.assertGreaterEqual(tokens_cn, 16)

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

    def test_point_7_watermark_dynamic_recovery_from_red_zone(self):
        """验证点 7: 消除永久红区陷阱，摘要压缩后水位能够动态真实回落"""
        ledger = BudgetLedger(total_budget=500, output_reserve=100, system_reserve=50, tools_reserve=50, memory_reserve=50)
        mgr = ContextManager("test_watermark_recovery", budget_ledger=ledger)

        for i in range(1, 5):
            mgr.start_new_turn(f"长轮次 {i} 提问 " + "a" * 80)
            mgr.add_assistant_message(f"长轮次 {i} 回答 " + "b" * 80)
            mgr.finish_current_turn()

        mgr.start_new_turn("当前提问")
        _, metrics_red = mgr.build_context_with_watermark("System Prompt", force_summary=True)
        self.assertEqual(metrics_red["zone"], WatermarkZone.RED)
        self.assertTrue(mgr.summarizer.state.has_summary())

        mgr.add_assistant_message("当前回答")
        mgr.finish_current_turn()

        mgr.start_new_turn("简短提问")
        _, metrics_recovered = mgr.build_context_with_watermark("System Prompt")

        self.assertIn(metrics_recovered["zone"], [WatermarkZone.GREEN, WatermarkZone.YELLOW])
        self.assertLess(metrics_recovered["raw_utilization"], 0.75)

        if mgr.history_file.exists():
            os.remove(mgr.history_file)

    def test_point_8_read_code_with_exception_not_mistaken_as_failure(self):
        """验证点 8: 读取包含 Error/Exception 关键字的代码正文绝不误判为读取失败"""
        wm = self.mgr.working_memory
        code_with_error_handling = (
            "def handle_request():\n"
            "    try:\n"
            "        do_something()\n"
            "    except Exception as e:\n"
            "        logger.error(f'Error occurred: {e}')\n"
            "        raise CustomError('FAILED')\n"
        )
        wm.update_from_tool("read_file", {"file_path": "core/agent.py"}, code_with_error_handling)
        self.assertIn("core/agent.py", wm.inspected_files, "包含错误处理代码的文件必须成功记录到已排查列表！")

        # 对照验证：真正的读取失败绝不记录
        wm.update_from_tool("read_file", {"file_path": "missing.py"}, "读取文件失败: [Errno 2] No such file or directory: 'missing.py'")
        self.assertNotIn("missing.py", wm.inspected_files, "真正读取报错的文件绝对不能记录进已排查列表！")

    def test_point_9_green_zone_no_duplicate_injection(self):
        """验证点 9: 绿区消除双重注入，已有摘要时活跃历史不重复包含已被摘要吸收的轮次"""
        mgr = ContextManager("test_no_dup", budget_ledger=self.ledger)
        # 构造第 1 轮并打上摘要
        mgr.start_new_turn("历史第 1 轮")
        mgr.add_assistant_message("历史回答 1")
        mgr.finish_current_turn()
        
        # 标记第 1 轮已被摘要覆盖
        mgr.summarizer.state.summary_text = "第 1 轮已排查完毕"
        mgr.summarizer.state.covered_through_turn_id = 1
        mgr.summarizer.state.start_turn_id = 1
        mgr.summarizer.state.end_turn_id = 1

        # 第 2 轮
        mgr.start_new_turn("历史第 2 轮")
        mgr.add_assistant_message("历史回答 2")
        mgr.finish_current_turn()

        # 第 3 轮提问（处于绿区）
        mgr.start_new_turn("当前第 3 轮提问")
        messages, metrics = mgr.build_context_with_watermark("System Prompt")

        # 核心断言：
        # 活跃历史消息中，绝不应再出现第 1 轮的原始对话内容（因为第 1 轮已在摘要中涵盖）！
        user_contents = [m.get("content") for m in messages if m.get("role") == "user"]
        self.assertNotIn("历史第 1 轮", user_contents, "已被摘要覆盖的早期轮次绝不应在活跃历史中重复注入！")
        self.assertTrue(any("历史第 2 轮" in c for c in user_contents), "未被摘要的较新轮次必须保留在活跃历史中！")

        if mgr.history_file.exists():
            os.remove(mgr.history_file)


    def test_point_10_prompt_cache_friendly_working_memory_position(self):
        """验证点 10: WorkingMemory 注入尾部用户消息，历史轮次稳态命中 Prompt Cache 且支持轮内实时更新"""
        mgr = ContextManager("test_cache_order", budget_ledger=self.ledger)

        # 历史轮次
        mgr.start_new_turn("历史问题 1")
        mgr.add_assistant_message("历史回答 1")
        mgr.finish_current_turn()

        # 当前轮次
        mgr.start_new_turn("当前提问: 修复模块")
        mgr.working_memory.update_from_tool("read_file", {"file_path": "core/agent.py"}, "def handle_request(): pass")

        messages, _ = mgr.build_context_with_watermark("Base System Prompt")

        # 核心断言 1: 前缀必须是稳态的 (system prompt 领先，紧随其后的是历史轮次)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], "Base System Prompt")

        # 历史消息必须紧跟在 system 之后，未被 WorkingMemory 破坏前缀
        history_user_idx = next(i for i, m in enumerate(messages) if m.get("role") == "user" and "历史问题 1" in m.get("content", ""))
        self.assertEqual(history_user_idx, 1, "历史第一轮消息必须在索引 1，前缀连续且稳态命中缓存")

        # 核心断言 2: WorkingMemory 必须注入到当前轮次的用户提问中 (位于尾部)
        curr_user_msg = messages[-1]
        self.assertEqual(curr_user_msg["role"], "user")
        self.assertIn("Working Memory", curr_user_msg["content"])
        self.assertIn("[用户当前提问]: 当前提问: 修复模块", curr_user_msg["content"])
        self.assertIn("core/agent.py", curr_user_msg["content"])

        if mgr.history_file.exists():
            os.remove(mgr.history_file)


    def test_point_11_apply_patch_tool_exact_recognition(self):
        """验证点 11: 精准对接 patch_tool.py 的【创建成功】和【补丁成功】前缀"""
        wm = self.mgr.working_memory

        # 1. 验证【创建成功】
        patch_create_args = {
            "patch_content": "*** Create File: src/new_module.py\n+ def hello(): pass"
        }
        create_res = "【创建成功】文件 'src/new_module.py' 已成功创建（共 25 字符）。"
        wm.update_from_tool("apply_patch", patch_create_args, create_res)
        self.assertIn("src/new_module.py", wm.modified_files, "【创建成功】的新文件必须被正确记录！")

        # 2. 验证【补丁成功】
        patch_update_args = {
            "patch_content": "*** Update File: src/existing.py\n@@ def f():\n- pass\n+ return 1"
        }
        update_res = "【补丁成功】文件 'src/existing.py' 已成功修改，共完成 1 处代码块替换。"
        wm.update_from_tool("apply_patch", patch_update_args, update_res)
        self.assertIn("src/existing.py", wm.modified_files, "【补丁成功】的修改文件必须被正确记录！")

        # 3. 对照验证：补丁失败绝对不记录
        fail_args = {
            "patch_content": "*** Update File: missing.py\n@@ def f():\n- pass\n+ return 1"
        }
        fail_res = "【补丁失败】目标文件 'missing.py' 不存在，无法应用更新补丁。"
        wm.update_from_tool("apply_patch", fail_args, fail_res)
        self.assertNotIn("missing.py", wm.modified_files, "执行失败的补丁绝对不能记录为修改！")

    def test_point_12_hard_gatekeeper_user_wm_compression(self):
        """验证点 12: 硬门禁超限时，能够成功对当前轮 user 消息中的 WorkingMemory 进行压缩与剥离"""
        ledger = BudgetLedger(
            total_budget=250,
            system_reserve=20,
            tools_reserve=20,
            memory_reserve=20,
            output_reserve=100,
            min_history_budget=20
        )
        mgr = ContextManager("test_gatekeeper_user_wm", budget_ledger=ledger)
        mgr.start_new_turn("请解决复杂的上下文溢出测试任务")

        # 添加多个排查文件使 WorkingMemory 变长
        for i in range(10):
            mgr.working_memory.update_from_tool(
                "read_file",
                {"file_path": f"module_{i}.py"},
                "def func(): pass"
            )

        # 构造超长活跃历史逼迫门禁触发
        for i in range(2):
            chunk = TurnChunk(turn_id=i+1)
            chunk.add_message({"role": "user", "content": "提问 " + "x" * 60})
            chunk.add_message({"role": "assistant", "content": "回答 " + "y" * 60})
            mgr.completed_turns.append(chunk)

        messages, metrics = mgr.build_context_with_watermark("System Base Prompt")
        self.assertTrue(metrics["hard_gatekeeper_triggered"], "必须触发硬门禁截断！")

        # 验证门禁触发后，最后一轮 user 消息保留了原始提问
        curr_user_msg = messages[-1]
        self.assertEqual(curr_user_msg["role"], "user")
        self.assertIn("请解决复杂的上下文溢出测试任务", curr_user_msg["content"], "硬门禁截断绝不能丢失用户核心提问！")

        if mgr.history_file.exists():
            import os
            os.remove(mgr.history_file)


    def test_point_13_react_inturn_dynamic_circuit_breaker(self):
        """验证点 13: ReAct 循环轮内动态 Token 预算核验与步间熔断（高优先级）"""
        from unittest.mock import MagicMock
        import json
        from core.agent import ReActAgent

        small_ledger = BudgetLedger(
            total_budget=200,
            system_reserve=20,
            tools_reserve=20,
            memory_reserve=20,
            output_reserve=50,
            min_history_budget=20
        )
        mgr = ContextManager("test_circuit_breaker", budget_ledger=small_ledger)
        if mgr.history_file.exists():
            os.remove(mgr.history_file)

        # 构造 Mock ReActAgent
        agent = ReActAgent.__new__(ReActAgent)
        agent.system_prompt = "You are a test agent."
        agent.max_steps = 5
        agent.model = "test-model"
        agent.context_manager = mgr
        agent.executor = MagicMock()
        agent.client = MagicMock()

        # Step 1: 返回工具调用与 API Usage
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "read_file"
        mock_tool_call.function.arguments = json.dumps({"file_path": "big_file.py"})

        msg_step1 = MagicMock()
        msg_step1.content = "I will read the big file."
        msg_step1.tool_calls = [mock_tool_call]

        resp_step1 = MagicMock()
        resp_step1.choices = [MagicMock(message=msg_step1)]
        resp_step1.usage.prompt_tokens = 60
        resp_step1.usage.completion_tokens = 30
        resp_step1.usage.total_tokens = 90

        # Step 2 的响应 (应被熔断拦截而不被调用)
        msg_step2 = MagicMock()
        msg_step2.content = "Final done"
        msg_step2.tool_calls = None
        resp_step2 = MagicMock()
        resp_step2.choices = [MagicMock(message=msg_step2)]

        agent.client.chat.completions.create.side_effect = [resp_step1, resp_step2]

        # Executor 返回超大内容，触发 Step 2 预算超标
        agent.executor.registry.get_schemas.return_value = []
        agent.executor.execute_tool_calls.return_value = [
            {"tool_call_id": "call_1", "content": "BIG DATA CONTENT " * 25}
        ]

        result = agent.run("请读取并处理超大文件", verbose=False)

        # 核心断言：Step 2 开头触发动态熔断并安全收敛
        self.assertIn("【系统保护】", result)
        self.assertEqual(len(agent.context_manager.completed_turns), 1)
        self.assertEqual(agent.client.chat.completions.create.call_count, 1, "熔断后绝不应再发起第 2 次大模型 API 调用！")
        self.assertEqual(agent.context_manager.last_api_prompt_tokens, 60, "成功捕获并记录了第 1 步的真实 API Usage！")

        if mgr.history_file.exists():
            os.remove(mgr.history_file)

    def test_point_14_inspected_file_range_merging_and_deduplication(self):
        """验证点 14: 工作区文件排查记录的区间合并与去重 (File Range Merging)"""
        wm = self.mgr.working_memory
        # 1. 首次读取 1-100 行
        wm.update_from_tool("read_file", {"file_path": "tools/calc.py", "start_line": 1, "max_lines": 100}, "content 1")
        self.assertEqual(wm.inspected_files["tools/calc.py"], "第 1 至 100 行")

        # 2. 连续排查 101-200 行 -> 智能合并为 1-200 行
        wm.update_from_tool("read_file", {"file_path": "tools/calc.py", "start_line": 101, "max_lines": 100}, "content 2")
        self.assertEqual(wm.inspected_files["tools/calc.py"], "第 1 至 200 行")

        # 3. 重复或包含排查 50-80 行 -> 仍在现有区间内，自动去重
        wm.update_from_tool("read_file", {"file_path": "tools/calc.py", "start_line": 50, "max_lines": 31}, "content 3")
        self.assertEqual(wm.inspected_files["tools/calc.py"], "第 1 至 200 行")

        # 4. 非连续排查 301-400 行 -> 拼接多区间
        wm.update_from_tool("read_file", {"file_path": "tools/calc.py", "start_line": 301, "max_lines": 100}, "content 4")
        self.assertEqual(wm.inspected_files["tools/calc.py"], "第 1 至 200 行; 第 301 至 400 行")

        # 5. 桥接排查 201-300 行 -> 完美打通并缝合为单一全区间 1-400 行
        wm.update_from_tool("read_file", {"file_path": "tools/calc.py", "start_line": 201, "max_lines": 100}, "content 5")
        self.assertEqual(wm.inspected_files["tools/calc.py"], "第 1 至 400 行")

    def test_point_15_log_compaction_and_vacuum(self):
        """验证点 15: 历史落盘文件的事务瘦身与垃圾回收机制 (Log Compaction / Vacuum)"""
        session_id = "test_vacuum_session"
        mgr = ContextManager(session_id, budget_ledger=self.ledger)
        if mgr.history_file.exists():
            os.remove(mgr.history_file)

        # 构造有效完成轮次 1 与 2
        mgr.start_new_turn("任务 1: 检查代码")
        mgr.working_memory.update_from_tool("read_file", {"file_path": "calc.py"}, "code")
        mgr.add_assistant_message("检查完毕")
        mgr.finish_current_turn()

        mgr.start_new_turn("任务 2: 编写测试")
        mgr.working_memory.update_from_tool("write_file", {"file_path": "test_calc.py"}, "ok")
        mgr.add_assistant_message("已写测试")
        mgr.finish_current_turn()

        # 制造废弃日志：开始第 3 轮然后回滚，开始第 4 轮然后中断 (abort)
        mgr.start_new_turn("任务 3: 临时尝试")
        mgr.add_assistant_message("尝试失败")
        mgr.finish_current_turn()
        mgr.rollback_last_turn()

        mgr.start_new_turn("任务 4: 意外中断的任务")
        mgr.abort_current_turn()

        # 统计压缩前的原始日志行数
        with open(mgr.history_file, "r", encoding="utf-8") as f:
            raw_lines = [l for l in f if l.strip()]
        self.assertGreater(len(raw_lines), 6, "含有 rollback 和 abort 的日志行数应较多")

        # 执行事务瘦身 Vacuum
        vacuum_success = mgr.vacuum()
        self.assertTrue(vacuum_success)

        # 统计压缩后的日志行数：应仅保留当前有效完成轮次（第 1 轮和第 2 轮）的紧凑记录
        with open(mgr.history_file, "r", encoding="utf-8") as f:
            compact_lines = [l for l in f if l.strip()]
        self.assertLess(len(compact_lines), len(raw_lines), "压缩后行数必须明显减少")

        # 核心断言：新实例从压缩日志还原，数据 100% 精准无损
        restored = ContextManager(session_id, budget_ledger=self.ledger)
        self.assertTrue(restored.restore_from_disk())
        self.assertEqual(len(restored.completed_turns), 2)
        self.assertEqual(restored.turn_count, 2)
        self.assertIn("test_calc.py", restored.working_memory.modified_files)
        self.assertIn("calc.py", restored.working_memory.inspected_files)

        # 验证 clear 后自动压缩
        mgr.clear()
        with open(mgr.history_file, "r", encoding="utf-8") as f:
            cleared_lines = [l for l in f if l.strip()]
        self.assertEqual(len(cleared_lines), 1, "clear 后执行 vacuum 应仅保留单条 session_cleared 记录")

        if mgr.history_file.exists():
            os.remove(mgr.history_file)

    def test_point_16_ground_truth_api_usage_tracking(self):
        """验证点 16: 接入大模型真实 API Usage 反馈校准 (Ground-Truth Token Calibration)"""
        mgr = ContextManager("test_api_usage", budget_ledger=self.ledger)
        self.assertEqual(mgr.last_api_prompt_tokens, 0)
        self.assertEqual(mgr.total_api_prompt_tokens, 0)

        # 第 1 步 API 调用反馈
        mgr.record_api_usage(prompt_tokens=1200, completion_tokens=150)
        self.assertEqual(mgr.last_api_prompt_tokens, 1200)
        self.assertEqual(mgr.last_api_completion_tokens, 150)
        self.assertEqual(mgr.total_api_prompt_tokens, 1200)
        self.assertEqual(mgr.total_api_completion_tokens, 150)

        # 第 2 步 API 调用反馈
        mgr.record_api_usage(prompt_tokens=1400, completion_tokens=200)
        self.assertEqual(mgr.last_api_prompt_tokens, 1400)
        self.assertEqual(mgr.last_api_completion_tokens, 200)
        self.assertEqual(mgr.total_api_prompt_tokens, 2600)
        self.assertEqual(mgr.total_api_completion_tokens, 350)

        # 验证 metrics 暴露
        _, metrics = mgr.build_context_with_watermark("System prompt")
        self.assertEqual(metrics["last_api_prompt_tokens"], 1400)
        self.assertEqual(metrics["last_api_completion_tokens"], 200)
        self.assertEqual(metrics["total_api_tokens"], 2950)

        if mgr.history_file.exists():
            os.remove(mgr.history_file)

    def test_point_17_goal_intent_prefix_trimming_and_heuristics(self):
        """验证点 17: 目标识别的前缀修剪与意图启发式增强"""
        mgr = ContextManager("test_goal_heuristics", budget_ledger=self.ledger)

        # 1. 验证前缀修剪函数单元逻辑
        self.assertEqual(
            ContextManager._extract_clean_goal("好的，请继续修改下一个方法"),
            "修改下一个方法"
        )
        self.assertEqual(
            ContextManager._extract_clean_goal("帮我优化这个函数并添加类型标注"),
            "优化这个函数并添加类型标注"
        )
        self.assertEqual(
            ContextManager._extract_clean_goal("改完它"),
            "改完它"
        )
        self.assertIsNone(ContextManager._extract_clean_goal("好的"))
        self.assertIsNone(ContextManager._extract_clean_goal("继续"))
        self.assertIsNone(ContextManager._extract_clean_goal("好的，继续"))
        self.assertIsNone(ContextManager._extract_clean_goal("ok"))

        # 2. 验证多轮对话中 WorkingMemory 目标流转
        # 第 1 轮：带有口语前缀，提取有效目标
        mgr.start_new_turn("好的，请帮我排查 calc.py 里的除零错误")
        self.assertEqual(mgr.working_memory.current_goal, "排查 calc.py 里的除零错误")
        mgr.add_assistant_message("正在排查")
        mgr.finish_current_turn()

        # 第 2 轮：纯推进停用词，保持上一轮目标不被口语覆写污染
        mgr.start_new_turn("好的，继续")
        self.assertEqual(mgr.working_memory.current_goal, "排查 calc.py 里的除零错误")
        mgr.add_assistant_message("已找到错误点")
        mgr.finish_current_turn()

        # 第 3 轮：简短有效指令（3字符），成功更新为新协同目标
        mgr.start_new_turn("改完它")
        self.assertEqual(mgr.working_memory.current_goal, "改完它")
        mgr.finish_current_turn()

        if mgr.history_file.exists():
            os.remove(mgr.history_file)

    def test_point_18_yellow_and_red_zone_candidate_deduplication(self):
        """验证点 18: 黄区与红区切分统一使用未压缩候选轮次，彻底杜绝与已有摘要产生双重注入"""
        ledger = BudgetLedger(total_budget=1000, output_reserve=100, system_reserve=50, tools_reserve=50, memory_reserve=50)
        mgr = ContextManager("test_candidate_dedup", budget_ledger=ledger)
        try:
            # 轮次 1 (约 50 tokens)
            mgr.start_new_turn("轮次 1 历史排查内容 " + "a" * 50)
            mgr.add_assistant_message("轮次 1 执行结果 " + "b" * 50)
            mgr.finish_current_turn()

            # 标记轮次 1 已被摘要覆盖
            mgr.summarizer.state.summary_text = "轮次 1 已被摘要覆盖纪要"
            mgr.summarizer.state.covered_through_turn_id = 1
            mgr.summarizer.state.start_turn_id = 1
            mgr.summarizer.state.end_turn_id = 1

            # 轮次 2: 注入较长内容使有效历史利用率落在 60% ~ 75% 之间 (黄区)
            mgr.start_new_turn("轮次 2 问题 " + "x" * 900)
            mgr.add_assistant_message("轮次 2 回答 " + "y" * 900)
            mgr.finish_current_turn()

            # 轮次 3 触发上下文组装
            mgr.start_new_turn("轮次 3 当前提问")
            messages, metrics = mgr.build_context_with_watermark("Base System Prompt")

            self.assertEqual(metrics["zone"], WatermarkZone.YELLOW, "应该命中黄区水位")
            user_messages = [m.get("content", "") for m in messages if m.get("role") == "user"]

            # 核心断言：已被摘要覆盖的轮次 1 绝不能再次出现在活跃 user 消息明文中
            has_turn_1_dup = any("轮次 1 历史排查内容" in content for content in user_messages)
            self.assertFalse(has_turn_1_dup, "黄区切分必须使用 uncompressed_turns，杜绝与摘要双重注入！")

            # 但未被摘要的轮次 2 必须被保存在活跃历史中
            has_turn_2 = any("轮次 2 问题" in content for content in user_messages)
            self.assertTrue(has_turn_2, "未被摘要覆盖的轮次 2 必须正常保存在活跃上下文中！")
        finally:
            if mgr.history_file.exists():
                try:
                    os.remove(mgr.history_file)
                except Exception:
                    pass

    def test_point_19_working_memory_exact_numerical_tuple_ranges(self):
        """验证点 19: WorkingMemory 内部采用精确数值元组维护多区间，即使外部折叠省略也不会丢失离散区间"""
        wm = self.mgr.working_memory
        # 依次读取 4 个离散区间
        wm.update_from_tool("read_file", {"file_path": "core/agent.py", "start_line": 1, "max_lines": 10}, "res")
        wm.update_from_tool("read_file", {"file_path": "core/agent.py", "start_line": 20, "max_lines": 10}, "res")
        wm.update_from_tool("read_file", {"file_path": "core/agent.py", "start_line": 40, "max_lines": 10}, "res")
        wm.update_from_tool("read_file", {"file_path": "core/agent.py", "start_line": 60, "max_lines": 10}, "res")

        # 验证内部精确数值列表
        self.assertEqual(
            wm._file_ranges["core/agent.py"],
            [(1, 10), (20, 29), (40, 49), (60, 69)]
        )
        # 外部展示应做紧凑省略折叠渲染
        self.assertIn("...", wm.inspected_files["core/agent.py"])
        self.assertIn("共 4 个区间", wm.inspected_files["core/agent.py"])

        # 第 5 次读取：读取与第 3 个区间相邻/重叠的 45~55 行
        wm.update_from_tool("read_file", {"file_path": "core/agent.py", "start_line": 45, "max_lines": 11}, "res")

        # 核心断言：第 3 个区间精确归并为 (40, 55)，全部 4 个区间完全保全，无任何区间被截断丢失
        self.assertEqual(
            wm._file_ranges["core/agent.py"],
            [(1, 10), (20, 29), (40, 55), (60, 69)],
            "内部数值元组应确保省略号中间的离散区间在后续读取与合并中 100% 精确保留！"
        )

        # 验证快照序列化与反序列化完整性
        dumped = wm.to_dict()
        self.assertIn("_file_ranges", dumped)
        restored_wm = self.mgr.working_memory.__class__()
        restored_wm.load_dict(dumped)
        self.assertEqual(restored_wm._file_ranges["core/agent.py"], [(1, 10), (20, 29), (40, 55), (60, 69)])

    def test_point_20_cli_status_token_usage_display(self):
        """验证点 20: 控制台 /status 与 /memory 命令正确展示 Token 预算与实际 API 消耗"""
        from io import StringIO
        import sys
        from cli.commands import handle_slash_command

        class DummyAgent:
            def __init__(self, mgr):
                self.model = "deepseek-chat"
                self.context_manager = mgr
                self.mcp_manager = type("DummyMcp", (), {"clients": {}})()
                self.executor = type("DummyExec", (), {"registry": type("DummyReg", (), {"get_tool_names": lambda self: ["test_tool"]})()})()

        agent = DummyAgent(self.mgr)
        self.mgr.record_api_usage(prompt_tokens=2500, completion_tokens=350)

        captured = StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            handled, should_exit = handle_slash_command(agent, "/status")
        finally:
            sys.stdout = old_stdout

        self.assertTrue(handled)
        self.assertFalse(should_exit)
        output = captured.getvalue()
        self.assertIn("当前 Token 预算: 上限 300 | 输出预留 60", output)
        self.assertIn("累计 API 消耗: 输入 2500 Tokens | 输出 350 Tokens", output)


    def test_point_21_view_file_outline_ast_and_wm_integration(self):
        """验证点 21: view_file_outline AST 语法树提取大纲及与 WorkingMemory 联动记录"""
        from tools.builtin.file_tools import view_file_outline
        
        # 提取真实存在的 context/budget.py 大纲
        outline = view_file_outline("context/budget.py")
        self.assertIn("class BudgetLedger", outline)
        self.assertIn("def get_remaining_budget", outline)

        # 验证 WorkingMemory 自动将 outline 识别并沉淀至 inspected_files
        wm = self.mgr.working_memory
        wm.update_from_tool("view_file_outline", {"file_path": "context/budget.py"}, outline)
        self.assertIn("context/budget.py", wm.inspected_files)
        self.assertIn("代码大纲", wm.inspected_files["context/budget.py"])

    def test_point_22_step_awareness_and_graceful_wrapup(self):
        """验证点 22: 步数进度倒计时感知与最终步优雅收拢"""
        from unittest.mock import MagicMock
        from core.agent import ReActAgent
        import json
        import tempfile
        import shutil

        temp_wrapup_dir = tempfile.mkdtemp(prefix="test_wrapup_")
        wrapup_ledger = BudgetLedger(total_budget=500, system_reserve=30, tools_reserve=30, memory_reserve=30, output_reserve=60)
        mgr = ContextManager("test_wrapup_session", budget_ledger=wrapup_ledger, base_dir=Path(temp_wrapup_dir))

        agent = ReActAgent.__new__(ReActAgent)
        agent.system_prompt = "You are a test agent."
        agent.max_steps = 2
        agent.model = "test-model"
        agent.context_manager = mgr
        agent.executor = MagicMock()
        agent.mcp_manager = MagicMock()
        agent.mcp_manager.get_all_tool_schemas.return_value = []
        agent.executor.registry.get_tool_names.return_value = ["dummy_tool"]
        agent.executor.registry.get_schemas.return_value = [{"type": "function", "function": {"name": "dummy_tool"}}]
        agent.executor.execute.return_value = "dummy result"
        agent.executor.execute_tool_calls.return_value = [{"tool_call_id": "call_step1", "content": "dummy result"}]

        # Step 1: 返回 tool call
        mock_tc = MagicMock()
        mock_tc.id = "call_step1"
        mock_tc.type = "function"
        mock_tc.function.name = "dummy_tool"
        mock_tc.function.arguments = "{}"
        
        msg_step1 = MagicMock()
        msg_step1.content = "I need to call dummy_tool."
        msg_step1.tool_calls = [mock_tc]
        resp_step1 = MagicMock()
        resp_step1.choices = [MagicMock(message=msg_step1)]
        resp_step1.usage = None

        # Step 2: 最终步，此时 call_tools 应为 None，返回最终文本
        msg_step2 = MagicMock()
        msg_step2.content = "经过排查，这是最终结论报告。"
        msg_step2.tool_calls = None
        resp_step2 = MagicMock()
        resp_step2.choices = [MagicMock(message=msg_step2)]
        resp_step2.usage = None

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [resp_step1, resp_step2]
        agent.client = mock_client

        final_res = agent.run("请分析当前系统", verbose=False)
        self.assertIn("最终结论报告", final_res)

        # 检查 Step 2 调用时的参数: tools 必须为 None (工具已被关闭以强制模型收口)
        call_args_list = mock_client.chat.completions.create.call_args_list
        self.assertEqual(len(call_args_list), 2)
        self.assertIsNotNone(call_args_list[0][1].get("tools"))
        self.assertIsNone(call_args_list[1][1].get("tools"))

        # 检查发给模型的 messages 中是否单调注入了步数倒计时 Banner (最新 tool 结果尾部追加，前缀逐字稳态)
        step2_messages = call_args_list[1][1]["messages"]
        all_contents = [str(m.get("content", "")) for m in step2_messages]
        self.assertTrue(any("当前执行进度: 第 2/2 步" in c for c in all_contents))
        self.assertTrue(any("本轮已达最终步" in c for c in all_contents))
        shutil.rmtree(temp_wrapup_dir, ignore_errors=True)

    def test_point_23_dynamic_budget_ledger_200k_default_and_elastic_expansion(self):
        """验证点 23: 默认 200K 基线硬预算账本、分账配额与按需 250k-500k 动态弹性阶梯扩展"""
        default_ledger = BudgetLedger()
        self.assertEqual(default_ledger.total_budget, 200000)
        self.assertEqual(default_ledger.system_reserve, 4000)
        self.assertEqual(default_ledger.tools_reserve, 6000)
        self.assertEqual(default_ledger.memory_reserve, 6000)
        self.assertEqual(default_ledger.output_reserve, 8000)
        self.assertEqual(default_ledger.history_budget, 176000)
        self.assertEqual(default_ledger.expansion_tiers, [200000, 250000, 350000, 500000])
        self.assertFalse(default_ledger.is_expanded)

        # 验证单步向上跃迁至 250k (Tier 1)
        stepped = default_ledger.step_up_tier()
        self.assertTrue(stepped)
        self.assertEqual(default_ledger.total_budget, 250000)
        self.assertEqual(default_ledger.history_budget, 226000)
        self.assertTrue(default_ledger.is_expanded)
        self.assertEqual(default_ledger.current_tier_index, 1)

        # 验证继续跃迁至 350k (Tier 2) 与 500k (Tier 3)
        self.assertTrue(default_ledger.step_up_tier())
        self.assertEqual(default_ledger.total_budget, 350000)
        self.assertTrue(default_ledger.step_up_tier())
        self.assertEqual(default_ledger.total_budget, 500000)
        # 到达最高梯队 500k，无法进一步向上跃迁
        self.assertFalse(default_ledger.step_up_tier())

        # 验证多级自动按需扩容 (expand_if_needed)
        test_ledger = BudgetLedger()
        # 当预估需求为 180,000 时，超过 200k 的 85% (170,000)，自动扩容至 250k (180k 在 250k 中占 72% < 85%)
        expanded = test_ledger.expand_if_needed(180000, threshold_ratio=0.85)
        self.assertTrue(expanded)
        self.assertEqual(test_ledger.total_budget, 250000)

        # 当预估需求升至 220,000 时，超过 250k 的 85% (212,500)，继续扩容至 350k
        expanded_mid = test_ledger.expand_if_needed(220000, threshold_ratio=0.85)
        self.assertTrue(expanded_mid)
        self.assertEqual(test_ledger.total_budget, 350000)

        # 当需求突发为 450,000 时，连跳至 500k 最高阶梯
        expanded_further = test_ledger.expand_if_needed(450000, threshold_ratio=0.85)
        self.assertTrue(expanded_further)
        self.assertEqual(test_ledger.total_budget, 500000)

        # 验证低水位连续冷却回退机制 (cooldown_and_contract)
        # Tier 3 (500k) 的上一级是 Tier 2 (350k)，350k * 0.70 = 245,000
        # 第 1 轮低水位：进入冷却观测期，不立即缩容
        contracted_1 = test_ledger.cooldown_and_contract(100000, lower_ratio=0.70)
        self.assertFalse(contracted_1)
        self.assertEqual(test_ledger.total_budget, 500000)
        self.assertEqual(test_ledger.consecutive_low_turns, 1)

        # 第 2 轮低水位：冷却周期完成，安全平滑缩容至 350k
        contracted_2 = test_ledger.cooldown_and_contract(100000, lower_ratio=0.70)
        self.assertTrue(contracted_2)
        self.assertEqual(test_ledger.total_budget, 350000)

        # 环境变量动态指定覆盖测试
        old_env = os.environ.get("AGENT_TOTAL_BUDGET")
        try:
            os.environ["AGENT_TOTAL_BUDGET"] = "128000"
            big_ledger = BudgetLedger()
            self.assertEqual(big_ledger.total_budget, 128000)
            self.assertEqual(big_ledger.history_budget, 115000)
        finally:
            if old_env is not None:
                os.environ["AGENT_TOTAL_BUDGET"] = old_env
            else:
                os.environ.pop("AGENT_TOTAL_BUDGET", None)


    def test_point_24_write_file_and_fuzzy_patch_tolerance(self):
        """验证点 24: write_file 覆盖写入及 apply_patch 行尾空白模糊容错"""
        from tools.builtin.file_tools import write_file
        from tools.builtin.patch_tool import apply_patch
        from pathlib import Path

        test_file = "test_fuzzy_patch_demo.txt"
        test_path = Path(test_file)
        if test_path.exists():
            test_path.unlink()

        try:
            # 1. 验证 write_file 成功写入
            w_res = write_file(test_file, "line 1  \nline 2    \nline 3\n")
            self.assertIn("【写入成功】", w_res)
            self.assertTrue(test_path.exists())

            # 验证 WorkingMemory 自动沉淀至 modified_files
            wm = self.mgr.working_memory
            wm.update_from_tool("write_file", {"file_path": test_file}, w_res)
            self.assertIn(test_file, wm.modified_files)

            # 2. 验证 write_file 拦截核心自身保护文件
            block_res = write_file("tools/file_tools.py", "corrupted")
            self.assertIn("【安全拦截】", block_res)

            # 3. 验证 apply_patch 行尾空白模糊容错 (原文件有末尾空格，SEARCH 块去除了末尾空格)
            patch_content = f"""*** Update File: {test_file}
<<<<<<< SEARCH
line 1
line 2
line 3
=======
line 1
line 2 modified
line 3
>>>>>>> REPLACE
"""
            p_res = apply_patch(patch_content)
            self.assertIn("【补丁成功】", p_res)
            updated_text = test_path.read_text(encoding="utf-8")
            self.assertIn("line 2 modified", updated_text)

        finally:
            if test_path.exists():
                test_path.unlink()

    def test_point_25_inturn_observation_pruning(self):
        """验证点 25: 轮内陈旧工具观察结果折叠 (In-turn Observation Pruning)"""
        from core.agent import ReActAgent

        agent = ReActAgent.__new__(ReActAgent)
        agent.context_manager = self.mgr
        self.mgr.start_new_turn("用户排查大文件")

        # 模拟 4 步工具返回 (前 2 步返回超大内容，后 2 步为最新内容)
        big_content_1 = "HEADER_LINE_1\n" + ("x" * 800) + "\nTAIL_LINE_1"
        big_content_2 = "HEADER_LINE_2\n" + ("y" * 800) + "\nTAIL_LINE_2"
        short_content_3 = "Step 3 tool result"
        short_content_4 = "Step 4 tool result"

        messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "排查目标"},
            {"role": "assistant", "content": "call 1", "tool_calls": [{"id": "c1"}]},
            {"role": "tool", "tool_call_id": "c1", "content": big_content_1},
            {"role": "assistant", "content": "call 2", "tool_calls": [{"id": "c2"}]},
            {"role": "tool", "tool_call_id": "c2", "content": big_content_2},
            {"role": "assistant", "content": "call 3", "tool_calls": [{"id": "c3"}]},
            {"role": "tool", "tool_call_id": "c3", "content": short_content_3},
            {"role": "assistant", "content": "call 4", "tool_calls": [{"id": "c4"}]},
            {"role": "tool", "tool_call_id": "c4", "content": short_content_4},
        ]

        # 阈值设为很小 (10 Tokens) 强制触发裁剪
        pruned_count = agent._prune_inturn_observations(messages, threshold_tokens=10)
        self.assertEqual(pruned_count, 2, "应只折叠倒数前 2 条超长 tool 消息")

        # 验证前两条消息被折叠，保留首尾，注入折叠提示
        self.assertIn("[历史观察结果已由 Agent 消化，正文已折叠", messages[3]["content"])
        self.assertIn("HEADER_LINE_1", messages[3]["content"])
        self.assertIn("TAIL_LINE_1", messages[3]["content"])

        self.assertIn("[历史观察结果已由 Agent 消化，正文已折叠", messages[5]["content"])
        self.assertIn("HEADER_LINE_2", messages[5]["content"])
        self.assertIn("TAIL_LINE_2", messages[5]["content"])

        # 验证最近的 2 条 tool 消息保持原样，绝不折叠
        self.assertEqual(messages[7]["content"], short_content_3)
        self.assertEqual(messages[9]["content"], short_content_4)

    def test_point_26_console_inherits_agent_max_steps(self):
        """验证点 26: 控制台启动项解除硬编码，正确继承配置最大步数"""
        with open("cli/console.py", "r", encoding="utf-8") as f:
            console_code = f.read()
        self.assertNotIn("agent = ReActAgent(max_steps=10)", console_code)
        self.assertIn("agent = ReActAgent()", console_code)


    def test_point_27_working_memory_turn_id_and_expanded_file_display(self):
        """验证点 27: 工作记忆记录修改轮次及放宽至 15 个文件展示带总量提示"""
        wm = self.mgr.working_memory
        wm.clear()

        # 模拟在第 1 轮修改了 calc.py，在第 3 轮修改了 agent.py
        wm.update_from_tool("write_file", {"file_path": "tools/calc.py"}, "【写入成功】", turn_id=1)
        wm.update_from_tool("write_file", {"file_path": "core/agent.py"}, "【写入成功】", turn_id=3)

        self.assertEqual(wm._modified_file_turns["tools/calc.py"], 1)
        self.assertEqual(wm._modified_file_turns["core/agent.py"], 3)

        prompt_text = wm.format_prompt_context()
        self.assertIn("`tools/calc.py` (轮次 #1)", prompt_text)
        self.assertIn("`core/agent.py` (轮次 #3)", prompt_text)

        # 模拟大量修改 (共 18 个文件)，验证上限放宽至 15 且带有总量统计提示
        for i in range(1, 19):
            wm.update_from_tool("write_file", {"file_path": f"mod_{i}.py"}, "【写入成功】", turn_id=i)

        rendered = wm.format_prompt_context()
        self.assertIn("累计已改 20 个文件", rendered)
        self.assertIn("早期前序省略 5 个", rendered)

        # 验证序列化与反序列化
        d = wm.to_dict()
        self.assertIn("_modified_file_turns", d)
        new_wm = wm.__class__()
        new_wm.load_dict(d)
        self.assertEqual(new_wm._modified_file_turns["tools/calc.py"], 1)
        self.assertEqual(new_wm._modified_file_turns["mod_18.py"], 18)

    def test_point_25_elastic_context_watermark_and_agent_inturn_expansion(self):
        """验证点 25: 动态弹性扩容与 ContextManager 水位联动以及 Agent 轮内步间动态跃迁"""
        import tempfile
        import shutil
        from core.agent import ReActAgent

        temp_dir = tempfile.mkdtemp(prefix="test_elastic_")
        try:
            # 1. 验证 ContextManager 在需求接近 85% 时自动从 200k 扩容至 250k
            ledger = BudgetLedger(
                total_budget=200000,
                base_budget=200000,
                max_expand_budget=500000,
                auto_expand=True
            )
            mgr = ContextManager("test_elastic_session", budget_ledger=ledger, base_dir=Path(temp_dir))

            # 注入历史轮次使需求触及高位 (约 180,000 tokens > 176k*0.85 = 149.6k)
            big_turn = TurnChunk(turn_id=1)
            big_turn.add_message({"role": "user", "content": "x" * 700000})  # ~184,000 tokens > 85%
            mgr.completed_turns.append(big_turn)
            mgr.turn_count = 1

            msgs, metrics = mgr.build_context_with_watermark("System Prompt")
            self.assertTrue(metrics["is_expanded"])
            self.assertEqual(metrics["max_budget"], 250000)
            self.assertEqual(metrics["tier_info"]["current_tier_index"], 1)
            self.assertEqual(mgr.budget.total_budget, 250000)

            # 2. 验证 ReActAgent 轮内多步累积导致超过基准上限时，优先触发弹性扩容而非直接截断熔断
            agent_ledger = BudgetLedger(
                total_budget=200,
                base_budget=200,
                max_expand_budget=500,
                auto_expand=True,
                expansion_tiers=[200, 300, 500],
                system_reserve=20,
                tools_reserve=20,
                memory_reserve=20,
                output_reserve=40,
                min_history_budget=20
            )
            agent_mgr = ContextManager("test_agent_expand", budget_ledger=agent_ledger, base_dir=Path(temp_dir))
            agent = ReActAgent(api_key="mock_test_key", context_manager=agent_mgr, max_steps=5)

            test_messages = [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "u" * (180 * 3)},
                {"role": "assistant", "content": "thinking"},
                {"role": "tool", "content": "tool result 1", "tool_call_id": "c1"}
            ]
            current_tokens = agent.context_manager.token_counter.count_messages(test_messages)
            max_allowed_before = agent.context_manager.budget.total_budget - agent.context_manager.budget.output_reserve - 20
            self.assertGreater(current_tokens, max_allowed_before)

            expanded = agent.context_manager.budget.expand_if_needed(current_tokens + 40 + 20)
            self.assertTrue(expanded)
            self.assertEqual(agent.context_manager.budget.total_budget, 300)
            max_allowed_after = agent.context_manager.budget.total_budget - agent.context_manager.budget.output_reserve - 20
            self.assertGreaterEqual(max_allowed_after, current_tokens)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()
