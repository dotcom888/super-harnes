# -*- coding: utf-8 -*-
import unittest
import os
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

if __name__ == "__main__":
    unittest.main()
