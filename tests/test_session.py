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
import tempfile
from pathlib import Path
from io import StringIO
import sys
from core.session import SessionManager
from core.agent import ReActAgent
from cli.commands import handle_slash_command

class TestMultiSessionManagement(unittest.TestCase):
    """验证多会话隔离、会话切换、自动唤醒与斜杠命令交互"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_sessions_dir_")
        self.history_dir = Path(self.temp_dir).resolve()
        self.sm = SessionManager(default_session_id="default", history_dir=self.history_dir)

    def tearDown(self):
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_multi_session_strict_isolation(self):
        """核心验证：不同会话间的短期滑窗、工作记忆与文件修改记录严格隔离，互不污染"""
        # 会话 A: 操作任务 A
        mgr_a = self.sm.switch_session("session_alpha")
        mgr_a.start_new_turn("任务 A: 修复 agent 模块")
        mgr_a.working_memory.update_from_tool("write_file", {"file_path": "core/agent.py"}, "ok")
        mgr_a.working_memory.update_goal("重构 agent", is_manual=True)
        mgr_a.add_assistant_message("已完成 agent 修复")
        mgr_a.finish_current_turn()

        # 切换到会话 B: 必须是空白会话
        mgr_b = self.sm.switch_session("session_beta")
        self.assertEqual(len(mgr_b.completed_turns), 0, "会话 B 必须无历史轮次")
        self.assertEqual(mgr_b.turn_count, 0)
        self.assertNotIn("core/agent.py", mgr_b.working_memory.modified_files)
        self.assertNotEqual(mgr_b.working_memory.current_goal, "重构 agent")

        # 会话 B 执行任务 B
        mgr_b.start_new_turn("任务 B: 优化 session 模块")
        mgr_b.working_memory.update_from_tool("write_file", {"file_path": "core/session.py"}, "ok")
        mgr_b.working_memory.update_goal("开发 session", is_manual=True)
        mgr_b.add_assistant_message("已完成 session 优化")
        mgr_b.finish_current_turn()

        # 切回会话 A: 任务 A 状态必须完好无损，且无会话 B 的任何记录
        mgr_a_again = self.sm.switch_session("session_alpha")
        self.assertEqual(len(mgr_a_again.completed_turns), 1)
        self.assertIn("core/agent.py", mgr_a_again.working_memory.modified_files)
        self.assertNotIn("core/session.py", mgr_a_again.working_memory.modified_files, "会话 A 绝不能被会话 B 污染")
        self.assertEqual(mgr_a_again.working_memory.current_goal, "重构 agent")

    def test_multi_session_auto_restore_on_switch(self):
        """核心验证：切换至未加载的已有磁盘会话时，无需输入 /restore，自动反序列化唤醒"""
        mgr = self.sm.switch_session("task_disk")
        mgr.start_new_turn("排查历史")
        mgr.working_memory.update_from_tool("read_file", {"file_path": "calc.py"}, "code")
        mgr.add_assistant_message("排查完成")
        mgr.finish_current_turn()

        self.assertTrue((self.history_dir / "task_disk.jsonl").exists())

        # 模拟重启：新建全新的 SessionManager 实例
        new_sm = SessionManager(default_session_id="default", history_dir=self.history_dir)
        self.assertEqual(new_sm.active_session_id, "default")

        # 切换到 task_disk: 自动触发 restore_from_disk
        restored_mgr = new_sm.switch_session("task_disk")
        self.assertEqual(restored_mgr.turn_count, 1)
        self.assertEqual(len(restored_mgr.completed_turns), 1)
        self.assertIn("calc.py", restored_mgr.working_memory.inspected_files)

    def test_create_and_delete_session(self):
        """验证会话创建、列表感知与安全删除（自动切回 default）"""
        mgr_new = self.sm.create_session("temp_session")
        self.assertEqual(self.sm.active_session_id, "temp_session")
        mgr_new.start_new_turn("临时记录")
        mgr_new.add_assistant_message("临时回复")
        mgr_new.finish_current_turn()

        self.assertTrue((self.history_dir / "temp_session.jsonl").exists())

        # 删除活动会话
        success = self.sm.delete_session("temp_session")
        self.assertTrue(success)
        self.assertFalse((self.history_dir / "temp_session.jsonl").exists(), "磁盘日志文件应被清理")
        self.assertEqual(self.sm.active_session_id, "default", "删除当前活动会话后必须自动切回 default")

    def test_rename_session_and_disk_migration(self):
        """验证会话重命名：内存及磁盘日志原子重命名，历史对齐"""
        mgr = self.sm.switch_session("old_name")
        mgr.start_new_turn("重命名测试")
        mgr.working_memory.update_from_tool("write_file", {"file_path": "test.txt"}, "ok")
        mgr.add_assistant_message("已写入")
        mgr.finish_current_turn()

        self.assertTrue((self.history_dir / "old_name.jsonl").exists())

        renamed = self.sm.rename_session("old_name", "new_name")
        self.assertTrue(renamed)
        self.assertFalse((self.history_dir / "old_name.jsonl").exists())
        self.assertTrue((self.history_dir / "new_name.jsonl").exists())
        self.assertEqual(self.sm.active_session_id, "new_name")

        active_mgr = self.sm.active_session
        self.assertEqual(active_mgr.session_id, "new_name")
        self.assertEqual(active_mgr.turn_count, 1)
        self.assertIn("test.txt", active_mgr.working_memory.modified_files)

    def test_get_session_preview_formatting(self):
        """验证会话快照与历史预览生成格式"""
        mgr = self.sm.switch_session("preview_session")
        mgr.working_memory.update_goal("实现预览功能", is_manual=True)
        mgr.start_new_turn("用户提问测试")
        mgr.add_assistant_message("助手答复测试")
        mgr.finish_current_turn()

        preview = self.sm.get_session_preview("preview_session")
        self.assertIn("会话 【preview_session】 上下文快照", preview)
        self.assertIn("实现预览功能", preview)
        self.assertIn("用户: 用户提问测试", preview)
        self.assertIn("助手: 助手答复测试", preview)

    def test_agent_session_delegation_and_setter(self):
        """验证 ReActAgent 与 SessionManager 的联动属性及代理方法"""
        agent = ReActAgent.__new__(ReActAgent)
        agent.session_manager = self.sm

        self.assertEqual(agent.context_manager.session_id, "default")
        agent.switch_session("session_via_agent")
        self.assertEqual(agent.context_manager.session_id, "session_via_agent")

        # 测试 setter 赋值
        custom_mgr = ContextManager("custom_session", base_dir=self.history_dir)
        agent.context_manager = custom_mgr
        self.assertEqual(agent.context_manager.session_id, "custom_session")
        self.assertEqual(agent.session_manager.active_session_id, "custom_session")

    def test_cli_slash_commands_multi_session(self):
        """验证命令行斜杠指令：/sessions, /switch, /session new, /status 等交互"""
        agent = ReActAgent.__new__(ReActAgent)
        agent.session_manager = self.sm
        agent.model = "deepseek-chat"
        agent.mcp_manager = type("DummyMcp", (), {"clients": {}})()
        agent.executor = type("DummyExec", (), {"registry": type("DummyReg", (), {"get_tool_names": lambda self: ["test_tool"]})()})()

        # 捕获 /sessions
        captured = StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            handled, should_exit = handle_slash_command(agent, "/sessions")
        finally:
            sys.stdout = old_stdout

        self.assertTrue(handled)
        self.assertFalse(should_exit)
        self.assertIn("会话列表", captured.getvalue())

        # 快捷切换 /switch task_feature
        captured = StringIO()
        try:
            sys.stdout = captured
            handled, should_exit = handle_slash_command(agent, "/switch task_feature")
        finally:
            sys.stdout = old_stdout

        self.assertTrue(handled)
        self.assertEqual(agent.session_manager.active_session_id, "task_feature")
        self.assertIn("当前激活会话: 【task_feature】", captured.getvalue())

        # 检查 /status 中的当前会话字段
        captured = StringIO()
        try:
            sys.stdout = captured
            handled, should_exit = handle_slash_command(agent, "/status")
        finally:
            sys.stdout = old_stdout

        self.assertIn("当前会话: 【task_feature】", captured.getvalue())

        # /session new 创建会话
        captured = StringIO()
        try:
            sys.stdout = captured
            handled, should_exit = handle_slash_command(agent, "/session new bug_fix_box")
        finally:
            sys.stdout = old_stdout

        self.assertEqual(agent.session_manager.active_session_id, "bug_fix_box")
        self.assertIn("新建会话成功", captured.getvalue())
    def test_react_inturn_prompt_cache_strict_append_only(self):
        """核心验证：ReAct 循环轮内严格单调追加 (Strict Append-Only)，User 消息前缀绝不回溯篡改，确保 100% KV Cache 命中"""
        from unittest.mock import MagicMock
        import json

        mgr = ContextManager("test_cache_append_only", base_dir=self.history_dir)
        agent = ReActAgent.__new__(ReActAgent)
        agent.system_prompt = "You are a coding assistant."
        agent.max_steps = 5
        agent.model = "deepseek-chat"
        agent.context_manager = mgr
        agent.client = MagicMock()
        agent.executor = MagicMock()
        agent.executor.registry.get_schemas.return_value = []

        # Step 1: 触发 write_file
        call_1 = MagicMock()
        call_1.id = "call_write"
        call_1.type = "function"
        call_1.function.name = "write_file"
        call_1.function.arguments = json.dumps({"file_path": "src/module.py", "content": "print('ok')"})

        msg_1 = MagicMock()
        msg_1.content = "I will write the file."
        msg_1.tool_calls = [call_1]
        resp_1 = MagicMock()
        resp_1.choices = [MagicMock(message=msg_1)]

        # Step 2: 最终解答
        msg_2 = MagicMock()
        msg_2.content = "File written successfully."
        msg_2.tool_calls = None
        resp_2 = MagicMock()
        resp_2.choices = [MagicMock(message=msg_2)]

        agent.client.chat.completions.create.side_effect = [resp_1, resp_2]
        agent.executor.execute_tool_calls.return_value = [
            {"tool_call_id": "call_write", "content": "【写入成功】文件 src/module.py 已更新"}
        ]

        # 记录调用前初始 User 提问（提问本身不包含 src/module.py 字眼）
        user_prompt = "请修复计算逻辑"
        recorded_user_msg_in_step2 = []

        def spy_create(*args, **kwargs):
            msgs = kwargs.get("messages", [])
            for m in msgs:
                if m.get("role") == "user" and user_prompt in m.get("content", ""):
                    recorded_user_msg_in_step2.append(m["content"])
            if len(recorded_user_msg_in_step2) == 1:
                return resp_1
            return resp_2

        agent.client.chat.completions.create.side_effect = spy_create

        result = agent.run(user_prompt, verbose=False)
        self.assertEqual(result, "File written successfully.")

        # 断言 1: 轮内 Working Memory 注记保持不可变（严禁轮内回写篡改 Working Memory）
        self.assertEqual(len(recorded_user_msg_in_step2), 2, "应执行两步大模型调用")
        wm_part_step1 = recorded_user_msg_in_step2[0].split("[用户当前提问]:")[0]
        wm_part_step2 = recorded_user_msg_in_step2[1].split("[用户当前提问]:")[0]
        # 轮内即使修改了文件，当前轮 User 消息的 Working Memory 也绝不回写追加 src/module.py
        self.assertNotIn("src/module.py", wm_part_step2, "轮内严禁回写 Working Memory 破坏前缀缓存！")

        # 断言 2: Python 内存中精确记录了修改
        self.assertIn("src/module.py", mgr.working_memory.modified_files)

        # 断言 3: 跨轮生效——开启下一轮后，新用户提问头部自动注入了上一轮修改的成果
        mgr.start_new_turn("下一步任务")
        new_msgs, _ = mgr.build_context_with_watermark("You are a coding assistant.")
        next_user_msg = next(m for m in new_msgs if m.get("role") == "user" and "下一步任务" in m.get("content", ""))
        self.assertIn("src/module.py", next_user_msg["content"], "新一轮的 Working Memory 注记中必须包含上一轮修改的文件！")
