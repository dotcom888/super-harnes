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

    def test_switch_workspace_and_cd_command(self):
        """验证 /cd 与 /workspace 动态切换工作区根目录"""
        from tools.framework.workspace import default_workspace
        agent = ReActAgent.__new__(ReActAgent)
        agent.session_manager = self.sm
        agent.model = "deepseek-chat"
        agent.mcp_manager = type("DummyMcp", (), {"clients": {}})()
        agent.executor = type("DummyExec", (), {"registry": type("DummyReg", (), {"get_tool_names": lambda self: ["test_tool"]})()})()

        sub_proj = Path(self.temp_dir) / "sub_project_demo"
        sub_proj.mkdir(parents=True, exist_ok=True)

        captured = StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            handled, should_exit = handle_slash_command(agent, f"/cd {sub_proj}")
        finally:
            sys.stdout = old_stdout

        self.assertTrue(handled)
        self.assertIn("工作区切换成功", captured.getvalue())
        self.assertEqual(default_workspace.root, sub_proj.resolve())
        self.assertEqual(agent.project_name, "sub_project_demo")
        self.assertEqual(agent.context_manager.session_id, "default")
        from config.settings import HISTORY_DIR
        sub_hist = HISTORY_DIR / "sub_project_demo"
        if sub_hist.exists():
            shutil.rmtree(sub_hist, ignore_errors=True)
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

class TestProjectLevelStateAndFusionWorkingMemory(unittest.TestCase):
    """核心验证：项目级目录分箱、跨会话工作记忆协同融合与长期摘要严格隔离"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_proj_hub_")
        self.root_path = Path(self.temp_dir).resolve()
        self.sm = SessionManager(
            default_session_id="default",
            base_dir=self.root_path,
            project_name="ecommerce_platform"
        )

    def tearDown(self):
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_project_physical_directory_isolation(self):
        """验证点 1: 项目级物理目录分箱，各个会话与 project_state.json 均收敛于 history/<project>/"""
        self.assertEqual(self.sm.project_name, "ecommerce_platform")
        self.assertEqual(self.sm.history_dir, self.root_path / "ecommerce_platform")

        mgr_cart = self.sm.switch_session("cart_service")
        mgr_cart.start_new_turn("重构购物车")
        mgr_cart.update_from_tool("write_file", {"file_path": "services/cart.py"}, "ok", turn_id=1)
        mgr_cart.finish_current_turn()

        # 检查物理目录中生成了对应的会话 jsonl 与项目状态 json
        cart_file = self.sm.history_dir / "cart_service.jsonl"
        state_file = self.sm.history_dir / "project_state.json"
        self.assertTrue(cart_file.exists(), "会话日志必须落在项目专有子目录内")
        self.assertTrue(state_file.exists(), "项目状态总线文件必须落盘在项目专有子目录内")

    def test_cross_session_fusion_working_memory_no_duplication(self):
        """验证点 2: 跨会话工作记忆看板融合 (Fusion View)，本会话与外部会话改动清晰区分，0 冗余"""
        # 会话 A (用户模块): 修改 user.py
        mgr_user = self.sm.switch_session("user_service")
        mgr_user.working_memory.update_goal("开发用户认证", is_manual=True)
        mgr_user.start_new_turn("任务 1: 用户模块")
        mgr_user.update_from_tool("write_file", {"file_path": "services/user.py"}, "ok", turn_id=1)
        mgr_user.finish_current_turn()

        # 切换到会话 B (订单模块): 修改 order.py
        mgr_order = self.sm.switch_session("order_service")
        mgr_order.working_memory.update_goal("优化下单链路", is_manual=True)
        mgr_order.start_new_turn("任务 2: 订单模块")
        mgr_order.update_from_tool("write_file", {"file_path": "services/order.py"}, "ok", turn_id=1)

        # 构造会话 B 的请求上下文
        messages, _ = mgr_order.build_context_with_watermark("System Prompt")
        user_msg = next(m["content"] for m in messages if m.get("role") == "user" and "任务 2" in m.get("content", ""))

        # 核心断言 1: 包含会话 B 专属私有目标，不包含会话 A 的私有目标
        self.assertIn("**当前会话协同目标**: 优化下单链路", user_msg)
        self.assertNotIn("开发用户认证", user_msg)

        # 核心断言 2: 【本会话已改代码】只展示 order.py
        self.assertIn("- **本会话已改代码**: `services/order.py`", user_msg)

        # 核心断言 3: 【项目其他会话协同改动】精准标出会话 A 改动的 user.py 及所属会话名
        self.assertIn("- **项目其他会话协同改动**", user_msg)
        self.assertIn("`services/user.py` (由会话 #user_service 在轮次 #1 修改)", user_msg)

        # 核心断言 4: 绝无重复注入
        self.assertEqual(user_msg.count("services/order.py"), 1, "本会话修改的文件绝不能在其他会话协同改动中重复出现")
        self.assertEqual(user_msg.count("services/user.py"), 1)

    def test_long_term_summary_strict_isolation_between_sessions(self):
        """验证点 3: 长期摘要保持会话级严格隔离，绝不跨对话框污染"""
        # 会话 A 注入专有历史摘要
        mgr_a = self.sm.switch_session("task_database")
        mgr_a.summarizer.state.summary_text = "数据库连接池排查结论: 最大连接数耗尽引发死锁。"
        mgr_a.summarizer.state.covered_through_turn_id = 2

        # 切换到会话 B
        mgr_b = self.sm.switch_session("task_frontend")
        mgr_b.start_new_turn("调整前端组件样式")
        messages_b, _ = mgr_b.build_context_with_watermark("Base System Prompt")

        # 核心断言: 会话 B 绝对看不到会话 A 的数据库死锁摘要
        all_content_b = " ".join([str(m.get("content", "")) for m in messages_b])
        self.assertNotIn("数据库连接池排查结论", all_content_b, "长期摘要必须严格归属当前对话框，绝不能跨会话污染！")
        self.assertFalse(mgr_b.summarizer.state.has_summary(), "新会话初始长期摘要必须为空")

    def test_project_state_rollback_synchronization(self):
        """验证点 4: 会话 /undo 回滚时，项目级状态总线精准联动撤销本会话该轮登记的改动"""
        mgr = self.sm.switch_session("rollback_test")
        mgr.start_new_turn("轮次 1: 写入 temp_tool.py")
        mgr.update_from_tool("write_file", {"file_path": "temp_tool.py"}, "ok", turn_id=1)
        mgr.finish_current_turn()

        # 验证已写入全局状态
        self.assertIn("temp_tool.py", self.sm.project_state.global_modified_files)

        # 执行回滚
        success = mgr.rollback_last_turn()
        self.assertTrue(success)

        # 核心断言: 项目全局状态中已同步清除该条修改记录
        self.assertNotIn("temp_tool.py", self.sm.project_state.global_modified_files, "回滚后全局状态总线中必须清除该轮改动！")


class TestGlobalUserMemory(unittest.TestCase):
    """验证用户级全局共享记忆 (~/.super-harnes/global_memory.json) 跨工程偏好沉淀与上下文构造顺序"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_global_mem_")
        self.mem_file = Path(self.temp_dir) / "global_memory.json"
        from context.global_memory import GlobalMemory
        self.gm = GlobalMemory(storage_path=self.mem_file)
        self.sm = SessionManager(default_session_id="default", base_dir=Path(self.temp_dir))

    def tearDown(self):
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_global_memory_persistence_and_habits(self):
        """验证全局偏好的增删、语言设置及原子落盘与反序列化"""
        self.assertTrue(self.mem_file.exists(), "初始化后应立即生成物理文件")

        # 添加偏好
        added = self.gm.add_habit("所有函数必须标注返回类型")
        self.assertTrue(added)
        self.assertIn("所有函数必须标注返回类型", self.gm.user_profile["coding_habits"])

        # 设置语言
        self.gm.set_language("English")
        self.assertEqual(self.gm.user_profile["language"], "English")

        # 新实例验证持久化
        from context.global_memory import GlobalMemory
        reloaded = GlobalMemory(storage_path=self.mem_file)
        self.assertEqual(reloaded.user_profile["language"], "English")
        self.assertIn("所有函数必须标注返回类型", reloaded.user_profile["coding_habits"])

        # 移除偏好
        removed = self.gm.remove_habit("返回类型")
        self.assertEqual(len(removed), 1)
        self.assertNotIn("所有函数必须标注返回类型", self.gm.user_profile["coding_habits"])

    def test_project_registry_and_lookup(self):
        """验证项目工作区索引地图的登记、查找与最近访问排序"""
        proj_dir = Path(self.temp_dir) / "demo_proj"
        proj_dir.mkdir()
        self.gm.register_project("demo_proj", proj_dir, "测试工程简介")

        found = self.gm.get_project("demo_proj")
        self.assertIsNotNone(found)
        self.assertEqual(found["path"], str(proj_dir.resolve()))
        self.assertEqual(found["description"], "测试工程简介")

        # 验证 list_projects
        projs = self.gm.list_projects()
        self.assertTrue(any(p["name"] == "demo_proj" for p in projs))

    def test_context_construction_full_order(self):
        """
        核心验证点 2: 构造请求时的端到端上下文顺序
        严格遵守：
        1. 头部: System Prompt (含 OS 环境感知 + 全局用户记忆偏好)
        2. 头部后续: 长期记忆摘要 (如果存在)
        3. 中部: 短期活跃历史轮次 (active_chunks: user -> assistant -> tool)
        4. 动态尾部: 当前轮首条 User 消息 (头部注入 Working Memory 项目与会话看板)
        5. 循环执行中追加: Assistant Tool Calls -> Tool Results
        """
        from core.prompt import build_system_prompt
        from context.manager import ContextManager
        from tools.framework.workspace import default_workspace

        # 1. 构造带有特定习惯的全局记忆
        self.gm.add_habit("代码测试必须使用 pytest")
        prompt_with_gm = build_system_prompt(global_memory=self.gm)
        self.assertIn("用户全局偏好与开发规范", prompt_with_gm)
        self.assertIn("代码测试必须使用 pytest", prompt_with_gm)

        # 2. 模拟 ContextManager 上下文构造
        mgr = ContextManager("test_order_session", base_dir=Path(self.temp_dir))
        # 第 1 轮（将被长期摘要覆盖）
        mgr.start_new_turn("历史提问 1")
        mgr.add_assistant_message("历史回答 1")
        mgr.finish_current_turn()

        # 设置长期摘要覆盖至轮次 1
        mgr.summarizer.state.summary_text = "历史排查结论: 修复了连接超时。"
        mgr.summarizer.state.covered_through_turn_id = 1

        # 写入短期历史第 2 轮（未被摘要覆盖，处于短期活跃滑窗）
        mgr.start_new_turn("历史提问 2")
        mgr.add_assistant_message("历史回答 2")
        mgr.finish_current_turn()

        # 开启当前轮（第 3 轮）
        mgr.start_new_turn("当前最新提问: 请重构订单模块")
        mgr.working_memory.update_goal("重构订单模块", is_manual=True)

        messages, metrics = mgr.build_context_with_watermark(prompt_with_gm)

        # 验证顺序 1: 首条消息必为 system，且包含全局记忆
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("用户全局偏好与开发规范", messages[0]["content"])

        # 验证顺序 2: 第 2 条消息必为长期摘要 system
        self.assertEqual(messages[1]["role"], "system")
        self.assertIn("历史排查结论: 修复了连接超时", messages[1]["content"])

        # 验证顺序 3: 随后是短期历史第 2 轮对话 (未被摘要覆盖的活跃轮次)
        self.assertEqual(messages[2]["role"], "user")
        self.assertIn("历史提问 2", messages[2]["content"])
        self.assertEqual(messages[3]["role"], "assistant")
        self.assertEqual(messages[3]["content"], "历史回答 2")

        # 验证顺序 4: 尾部为当前轮 User 消息，其内容头部包含 Working Memory 注记，后部包含用户提问正文
        cur_user_msg = messages[4]
        self.assertEqual(cur_user_msg["role"], "user")
        self.assertIn("【系统注记 - 项目与工作区感知状态 (Working Memory)】", cur_user_msg["content"])
        self.assertIn("[用户当前提问]: 当前最新提问: 请重构订单模块", cur_user_msg["content"])

    def test_cli_global_memory_commands(self):
        """验证控制台指令：/remember, /forget, /profile, /projects 以及通过工程名 /cd"""
        from core.agent import ReActAgent
        from cli.commands import handle_slash_command

        agent = ReActAgent.__new__(ReActAgent)
        agent.session_manager = self.sm
        agent.model = "deepseek-chat"
        agent.mcp_manager = type("DummyMcp", (), {"clients": {}})()
        agent.executor = type("DummyExec", (), {"registry": type("DummyReg", (), {"get_tool_names": lambda self: ["test_tool"]})()})()

        # 测试 /remember
        captured = StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            handled, _ = handle_slash_command(agent, "/remember 统一使用 UTF-8 编码")
        finally:
            sys.stdout = old_stdout
        self.assertTrue(handled)
        self.assertIn("全局记忆已更新", captured.getvalue())

        # 测试 /profile
        captured = StringIO()
        try:
            sys.stdout = captured
            handled, _ = handle_slash_command(agent, "/profile")
        finally:
            sys.stdout = old_stdout
        self.assertTrue(handled)
        self.assertIn("用户全局共享记忆", captured.getvalue())
        self.assertIn("统一使用 UTF-8 编码", captured.getvalue())

        # 测试 /projects
        captured = StringIO()
        try:
            sys.stdout = captured
            handled, _ = handle_slash_command(agent, "/projects")
        finally:
            sys.stdout = old_stdout
        self.assertTrue(handled)
        self.assertIn("已登记工程工作区地图", captured.getvalue())

        # 测试 /forget
        captured = StringIO()
        try:
            sys.stdout = captured
            handled, _ = handle_slash_command(agent, "/forget UTF-8")
        finally:
            sys.stdout = old_stdout
        self.assertTrue(handled)
        self.assertIn("已移除", captured.getvalue())
