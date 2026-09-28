# -*- coding: utf-8 -*-
"""
tests/test_cli_ui.py: 终端 Claude Code 风格 UI 模块单元测试套件
"""
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from io import StringIO

from cli.ui import TerminalUI, ClaudeTheme, default_ui


class TestClaudeCodeUI(unittest.TestCase):
    def setUp(self):
        self.ui = TerminalUI()
        self.ui.activate()

    def test_banner_rendering(self):
        """验证启动横幅正常渲染且包含必要元数据"""
        with patch.object(self.ui.console, "print") as mock_print:
            self.ui.render_banner(
                workspace_path=Path("E:/study/super-harnes"),
                project_name="super-harnes",
                session_id="default",
                model="deepseek-chat",
                native_tools=["run_shell", "read_file"],
                mcp_tools=["weather"]
            )
            self.assertTrue(mock_print.called)

    def test_tool_card_rendering_bash(self):
        """验证 Bash 工具调用卡片渲染 (● Bash + IN/OUT 网格)"""
        with patch.object(self.ui.console, "print") as mock_print:
            self.ui.render_tool_card(
                tool_name="run_shell",
                args={"command": "git status -s"},
                result=" M core/agent.py\n?? cli/ui.py",
                is_error=False,
                elapsed=0.15
            )
            self.assertTrue(mock_print.called)
            # 校验至少输出了标题、面板和空行
            self.assertGreaterEqual(mock_print.call_count, 2)

    def test_tool_card_rendering_patch(self):
        """验证代码补丁 Diff 输出高亮渲染"""
        with patch.object(self.ui.console, "print") as mock_print:
            diff_text = "--- a/test.py\n+++ b/test.py\n@@ -1,2 +1,2 @@\n-old\n+new\n"
            self.ui.render_tool_card(
                tool_name="patch_file",
                args={"file_path": "test.py"},
                result=diff_text,
                is_error=False
            )
            self.assertTrue(mock_print.called)

    def test_thinking_rendering(self):
        """验证思考指示器正常输出"""
        with patch.object(self.ui.console, "print") as mock_print:
            self.ui.render_thinking("正在进行全局代码走查与边界探索...")
            self.assertTrue(mock_print.called)

    def test_assistant_markdown_response(self):
        """验证 Markdown 排版正常渲染"""
        with patch.object(self.ui.console, "print") as mock_print:
            md_text = "### 结论与方案\n\n已完成全部审查。\n\n1. **重构点一**: 修复编码。\n2. **重构点二**: 增强 UI。"
            self.ui.render_assistant_response(md_text)
            self.assertTrue(mock_print.called)

    def test_token_usage_rendering(self):
        """验证轻量 Token 状态栏输出"""
        with patch.object(self.ui.console, "print") as mock_print:
            self.ui.render_token_usage(prompt_tokens=5000, comp_tokens=200, total_tokens=5200, model="deepseek-chat")
            self.assertTrue(mock_print.called)

    def test_approval_prompt_auto_reject_on_eof(self):
        """验证人机协同安全审批在无交互输入时安全拒绝"""
        with patch("builtins.input", side_effect=EOFError):
            approved = self.ui.render_approval_prompt("rm -rf tmp", "Dangerous operation")
            self.assertFalse(approved)

    def test_approval_prompt_approved(self):
        """验证用户手动确认批准"""
        with patch("builtins.input", return_value="y"):
            approved = self.ui.render_approval_prompt("git push", "State change")
            self.assertTrue(approved)

    def test_help_table(self):
        """验证 /help 指令表格渲染"""
        with patch.object(self.ui.console, "print") as mock_print:
            self.ui.render_help()
            self.assertTrue(mock_print.called)

    def test_sessions_table(self):
        """验证 /sessions 会话表格渲染"""
        with patch.object(self.ui.console, "print") as mock_print:
            sessions = [
                {"session_id": "default", "is_active": True, "turn_count": 2, "modified_files_count": 1, "has_disk_file": True, "current_goal": "Refactor"}
            ]
            self.ui.render_sessions_table(sessions, "super-harnes")
            self.assertTrue(mock_print.called)

    def test_user_prompt_rendering(self):
        """验证 OpenCode 风格用户提问独立卡片正常渲染"""
        with patch.object(self.ui.console, "print") as mock_print:
            self.ui.render_user_prompt("帮我跑一下测试并检查覆盖率", "test_proj", "session_1")
            self.assertTrue(mock_print.called)

    def test_interactive_command_palette_fallback(self):
        """验证非交互终端下命令中心平滑降级渲染帮助表格"""
        with patch.object(self.ui, "render_help") as mock_help:
            chosen = self.ui.interactive_command_palette()
            self.assertIsNone(chosen)
            mock_help.assert_called_once()


if __name__ == "__main__":
    unittest.main()
