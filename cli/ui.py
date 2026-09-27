# -*- coding: utf-8 -*-
"""
cli/ui.py: 工业级终端 UI 渲染引擎 (高保真复刻 Claude Code CLI 设计)
基于 Rich + prompt_toolkit 实现沉浸式、极简且高信息密度的交互式终端体验。
"""
import os
import sys
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.box import ROUNDED, SIMPLE

# 确保 Windows 终端 UTF-8 编码支持
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


class ClaudeTheme:
    """Claude Code 风格调色板与视觉规范"""
    # 颜色常数
    COLOR_SUCCESS = "#34d399"    # 翠绿 (工具成功/就绪)
    COLOR_THINKING = "#9ca3af"   # 柔灰 (思考折叠)
    COLOR_ASSISTANT = "#f3f4f6"  # 银白 (助手回复)
    COLOR_ERROR = "#f87171"      # 珊瑚红 (报错阻断)
    COLOR_WARN = "#fbbf24"       # 琥珀黄 (审批/警告)
    COLOR_INFO = "#38bdf8"       # 天青蓝 (文件/查询)
    COLOR_PURPLE = "#c084fc"     # 紫色 (MCP)

    # 徽章样式
    BADGE_IN = "bold black on bright_white"
    BADGE_OUT = "bold black on bright_white"
    BADGE_WARN = "bold black on #fbbf24"
    BADGE_ERR = "bold white on #dc2626"

    # 边框与暗调背景
    BORDER_DIM = "#374151"       # 浅暗灰边框
    BORDER_PANEL = "#4b5563"     # 容器外边框
    TEXT_DIM = "#9ca3af"         # 弱化文本色 (快捷键、用量)


from prompt_toolkit.completion import Completer, Completion


class SlashCommandCompleter(Completer):
    """
    仿现代 IDE 悬浮弹窗的斜杠命令智能补全器 (复刻图三现代交互)：
    - 呈现等宽清晰命令与中文分类详细描述
    - 配合深色圆角高亮条与右侧滑块，彻底消除 90 年代灰色死板弹窗感
    """
    COMMANDS = [
        ("/help", "查看全部可用控制指令手册与用法", "基础指南"),
        ("/auto", "切换至类似 Claude 的 AUTO 全自动免打扰执行模式", "权限控制"),
        ("/ask", "切换至敏感命令逐条人工审批模式", "权限控制"),
        ("/mode", "查看或切换当前安全审批模式 (auto / ask)", "权限控制"),
        ("/status", "查看当前 Working Memory、已读改文件与 MCP", "状态排查"),
        ("/memory", "查看当前工作区感知记忆与工具挂载", "状态排查"),
        ("/history", "查看当前会话已完成轮次的交互摘要", "状态排查"),
        ("/undo", "回滚上一轮对话，物理还原被修改的代码文件", "执行控制"),
        ("/new", "清空当前上下文记忆，开启全新排查任务", "会话管理"),
        ("/reset", "清空当前上下文记忆，重置排查环境", "会话管理"),
        ("/restore", "从本地磁盘归档目录中恢复历史会话", "会话管理"),
        ("/sessions", "列出当前工程所有历史与激活会话列表", "会话管理"),
        ("/switch", "切换并载入指定会话的历史上下文快照", "会话管理"),
        ("/cd", "切换当前智能体操作的目标工程工作区根目录", "工作区"),
        ("/workspace", "查看或校验当前工作区根目录与项目归属", "工作区"),
        ("/projects", "查看所有已登记的工程工作区索引地图", "全局索引"),
        ("/profile", "查看用户全局编码规范画像与开发习惯", "开发画像"),
        ("/remember", "永久记入一条跨工程生效的全局编程偏好", "开发画像"),
        ("/forget", "从全局记忆中移除指定的规则偏好", "开发画像"),
        ("exit", "安全保存并退出 Super-Harnes 智能体终端", "系统退出"),
        ("quit", "安全保存并退出 Super-Harnes 智能体终端", "系统退出"),
    ]


    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        # 仅在输入以 / 开头，或刚好在输入命令时提示
        if not text.startswith('/'):
            if text:
                return
        prefix = text.lower()
        for cmd, desc, cat in self.COMMANDS:
            if cmd.lower().startswith(prefix) or (prefix and prefix in cmd.lower()):
                yield Completion(
                    text=cmd,
                    start_position=-len(text),
                    display=f"  {cmd:<13} ",
                    display_meta=f" [{cat}] {desc} "
                )


class TerminalUI:
    """
    终端 UI 渲染引擎：
    全面复刻 Claude Code 的卡片化工具调用、Thinking 折叠指示、
    Markdown 排版美化、低噪 Token 状态栏与交互式安全审批卡片。
    """
    def __init__(self):
        self.console = Console(force_terminal=True, highlight=False, soft_wrap=True)
        self.is_active = False
        self._history_file = Path.home() / ".super-harnes" / "cli_history"
        self._prompt_session = None
        self._init_history_dir()

    def _init_history_dir(self):
        try:
            self._history_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def activate(self):
        """激活现代化 Claude Code 风格终端 UI"""
        self.is_active = True
        self._init_prompt_toolkit()

    def deactivate(self):
        """停用现代 UI（降级为原始平铺文本日志）"""
        self.is_active = False

    def _init_prompt_toolkit(self):
        """安全初始化 prompt_toolkit（支持鼠标滚轮与点击选择、现代化深色圆角滑块风格）"""
        try:
            from prompt_toolkit.shortcuts import PromptSession, CompleteStyle
            from prompt_toolkit.history import FileHistory
            from prompt_toolkit.styles import Style

            pt_style = Style.from_dict({
                # 底部低对比度提示条
                "bottom-toolbar": "bg:#18181b #718096",
                "bottom-toolbar.text": "#a1a1aa",

                # 补全菜单浮层主背景与柔和文本（告别90年代刺眼灰底白字）
                "completion-menu": "bg:#18181b #e4e4e7",
                "completion-menu.completion": "bg:#18181b #d1d5db",

                # 选中项：仿图三现代编辑器的深灰高亮胶囊条，纯白加粗
                "completion-menu.completion.current": "bold #ffffff bg:#323238",

                # 右侧中文元信息描述（微弱次级文本）
                "completion-menu.meta": "bg:#18181b #8a919e",
                "completion-menu.meta.completion.current": "bg:#323238 #93c5fd",

                # 滚动条滑块与轨道（精细平滑深调，支持鼠标控制）
                "scrollbar.background": "bg:#18181b",
                "scrollbar.button": "bg:#52525b",
                "scrollbar.arrow": "bg:#18181b #718096",

                # 提示符文本高亮
                "prompt": "#34d399 bold",
            })

            completer = SlashCommandCompleter()
            self._prompt_session = PromptSession(
                history=FileHistory(str(self._history_file)),
                completer=completer,
                complete_style=CompleteStyle.COLUMN,
                style=pt_style,
                mouse_support=True
            )
        except Exception:
            # 运行于子进程/无 Windows 控制台句柄时平滑退化
            self._prompt_session = None

    # -------------------------------------------------------------------------
    # 1. 启动横幅与状态概览 (Startup Banner)
    # -------------------------------------------------------------------------
    def render_banner(
        self,
        workspace_path: Path,
        project_name: str,
        session_id: str,
        model: str,
        native_tools: List[str],
        mcp_tools: List[str]
    ):
        """呈现极简且具工业美感的启动卡片"""
        header_text = Text()
        header_text.append(" ● SUPER-HARNES ", style=f"bold {ClaudeTheme.COLOR_SUCCESS}")
        header_text.append("本地自主代码智能体 (Local Coding Agent)", style="dim #9ca3af")

        meta_table = Table.grid(padding=(0, 1))
        meta_table.add_column(style="bold #9ca3af", justify="right")
        meta_table.add_column(style="white")

        meta_table.add_row("工作区根目录", f"[bold cyan]{workspace_path}[/] [dim]({project_name})[/]")
        meta_table.add_row("激活会话", f"[bold magenta]{session_id}[/]  [dim]|[/]  推理模型: [bold #38bdf8]{model}[/]")
        meta_table.add_row(
            "可用能力",
            f"[green]{len(native_tools)} 个内置工具[/green] [dim]({', '.join(native_tools[:4])}...)[/]  "
            f"[dim]|[/]  MCP 扩展: [purple]{len(mcp_tools)} 个动态工具[/purple]"
        )

        try:
            from tools.framework.policies import default_policy
            if default_policy.mode in ("auto", "never"):
                mode_badge = "[bold green]AUTO (类似 Claude 免打扰自动执行)[/]"
            elif default_policy.session_approved:
                mode_badge = "[bold green]ASK (会话已临时全部放行)[/]"
            elif default_policy.mode == "always_ask":
                mode_badge = "[bold red]ALWAYS_ASK (严格逐条人工审批)[/]"
            else:
                mode_badge = "[bold yellow]ASK (敏感操作交互审批)[/]"
            meta_table.add_row(
                "安全模式",
                f"{mode_badge}  [dim]|  输入 [white]/auto[/] 或 [white]/ask[/] 随时切换模式[/]"
            )
        except Exception:
            pass

        banner_panel = Panel(
            meta_table,
            title=header_text,
            title_align="left",
            border_style=ClaudeTheme.BORDER_DIM,
            padding=(0, 1)
        )
        self.console.print()
        self.console.print(banner_panel)
        self.console.print("[dim #6b7280]  💡 提示: 输入 [white]/help[/] 查看指令手册 · [white]Tab[/] 键智能补全 (支持鼠标点击/滚动选择) · [white]Ctrl+C[/] 中断当前轮次[/]\n")


    # -------------------------------------------------------------------------
    # 2. 核心：工具调用卡片 (Tool Execution Card: ● Bash / ReadFile / Edit ...)
    # -------------------------------------------------------------------------
    def _map_tool_title(self, tool_name: str) -> Tuple[str, str]:
        """将内部工具名转换为 Claude 风格的标准展示名与色彩"""
        mapping = {
            "run_shell": ("Bash", ClaudeTheme.COLOR_SUCCESS),
            "read_file": ("ReadFile", ClaudeTheme.COLOR_INFO),
            "write_file": ("WriteFile", ClaudeTheme.COLOR_SUCCESS),
            "patch_file": ("Edit", ClaudeTheme.COLOR_WARN),
            "grep_text": ("Grep", ClaudeTheme.COLOR_INFO),
            "find_by_name": ("Glob", ClaudeTheme.COLOR_INFO),
            "list_directory": ("ListDir", ClaudeTheme.COLOR_INFO)
        }
        if tool_name in mapping:
            return mapping[tool_name]
        if tool_name.startswith("mcp__"):
            parts = tool_name.split("__", 2)
            srv = parts[1] if len(parts) > 1 else "mcp"
            fn = parts[2] if len(parts) > 2 else tool_name
            return (f"MCP:{srv} > {fn}", ClaudeTheme.COLOR_PURPLE)
        return (tool_name, ClaudeTheme.COLOR_SUCCESS)

    def _format_tool_input(self, tool_name: str, args: Dict[str, Any]) -> str:
        """根据工具类型精炼提取最符合人类直觉的 IN 指令参数"""
        if not isinstance(args, dict):
            return str(args)
        if tool_name == "run_shell":
            return args.get("command", "")
        if tool_name == "read_file":
            path = args.get("file_path", "")
            sl = args.get("start_line")
            el = args.get("end_line")
            if sl or el:
                return f"{path} (lines {sl or 1}-{el or 'end'})"
            return str(path)
        if tool_name in ("patch_file", "write_file"):
            return str(args.get("file_path", ""))
        if tool_name == "grep_text":
            kw = args.get("keyword", "")
            d = args.get("directory", ".")
            return f"pattern '{kw}' in {d}"
        if tool_name == "find_by_name":
            return f"pattern '{args.get('pattern', '')}' in {args.get('directory', '.')}"
        return json.dumps(args, ensure_ascii=False)

    def render_tool_card(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Optional[str] = None,
        is_error: bool = False,
        elapsed: Optional[float] = None
    ):
        """
        高保真复刻 Claude Code 的工具执行卡片：
        ● Bash
        ┌─────────────────────────────────────────────────────────────┐
        │  IN   git show 7811c61:tools/framework/executor.py          │
        │                                                             │
        │  OUT  workers = min(self.max_workers, len(read_chunk))      │
        │       pool = concurrent.futures.ThreadPoolExecutor(...)     │
        └─────────────────────────────────────────────────────────────┘
        """
        display_name, accent_color = self._map_tool_title(tool_name)
        dot_color = ClaudeTheme.COLOR_ERROR if is_error else accent_color

        # 1. 顶部标题栏：● ToolName (可选耗时)
        title_text = Text()
        title_text.append("● ", style=f"bold {dot_color}")
        title_text.append(display_name, style="bold white")
        if elapsed is not None:
            title_text.append(f" ({elapsed:.2f}s)", style="dim")
        self.console.print(title_text)

        # 2. 卡片内部：IN / OUT 网格对齐
        grid = Table.grid(padding=(0, 1))
        grid.add_column(no_wrap=True)
        grid.add_column()

        # IN 行
        in_content = self._format_tool_input(tool_name, args)
        grid.add_row(
            Text(" IN ", style=ClaudeTheme.BADGE_IN),
            Text(f" {in_content}", style="bold white")
        )

        # OUT 行（若有）
        if result is not None:
            clean_res = result.strip()
            grid.add_row(Text(""), Text(""))  # 空间隔

            badge_text = " OUT " if not is_error else " ERR "
            badge_style = ClaudeTheme.BADGE_OUT if not is_error else ClaudeTheme.BADGE_ERR

            if tool_name == "patch_file" and ("--- " in clean_res or "@@ " in clean_res):
                diff_syntax = Syntax(clean_res, "diff", theme="monokai", line_numbers=False)
                grid.add_row(Text(badge_text, style=badge_style), diff_syntax)
            else:
                lines = clean_res.splitlines()
                if len(lines) > 20:
                    head_lines = lines[:12]
                    tail_lines = lines[-4:]
                    omitted_count = len(lines) - 16
                    preview_text = "\n".join(head_lines) + f"\n\n... ({omitted_count} lines truncated) ...\n\n" + "\n".join(tail_lines)
                else:
                    preview_text = clean_res

                # 代码语法高亮识别
                ext = Path(args.get("file_path", "")).suffix.lstrip(".") if isinstance(args, dict) else ""
                lexer_map = {"py": "python", "json": "json", "js": "javascript", "ts": "typescript", "md": "markdown", "sh": "bash"}
                syntax_lang = lexer_map.get(ext)

                if syntax_lang and len(lines) > 1:
                    code_syntax = Syntax(preview_text, syntax_lang, theme="monokai", line_numbers=False)
                    grid.add_row(Text(badge_text, style=badge_style), code_syntax)
                else:
                    grid.add_row(
                        Text(badge_text, style=badge_style),
                        Text(f" {preview_text}", style="cyan" if not is_error else "red")
                    )

        panel = Panel(grid, border_style=ClaudeTheme.BORDER_DIM, padding=(0, 1), expand=False)
        self.console.print(panel)
        self.console.print()

    # -------------------------------------------------------------------------
    # 3. 思考指示器 (Thinking Indicator: ● Thinking >)
    # -------------------------------------------------------------------------
    def render_thinking(self, thought_text: str):
        """
        呈现 Claude Code 风格的思考指示器：
        ● Thinking >
        柔灰暗调呈现，不刺眼，保持交互主界面的纯粹。
        """
        if not thought_text or not thought_text.strip():
            return

        header = Text()
        header.append("● ", style="dim #9ca3af")
        header.append("Thinking >", style="dim bold #9ca3af")
        self.console.print(header)

        # 以缩进暗灰色块呈现思考摘要
        clean_thought = thought_text.strip()
        lines = clean_thought.splitlines()
        preview = lines[0] if len(lines) == 1 else (lines[0] + " ...")
        if len(preview) > 120:
            preview = preview[:118] + "..."

        self.console.print(Text(f"  {preview}\n", style="dim #6b7280"))

    # -------------------------------------------------------------------------
    # 4. 助手最终回复 (Assistant Markdown Typography)
    # -------------------------------------------------------------------------
    def render_assistant_response(self, markdown_text: str):
        """
        高保真复刻 Claude Code 的助手回复排版：
        ● 开头引导，纯净的 Markdown 语法高亮、代码块与表格美化。
        """
        clean_md = markdown_text.strip()
        if not clean_md:
            return

        # 判断首行是否已经带有圆点
        if not clean_md.startswith("●"):
            clean_md = f"● {clean_md}"

        md = Markdown(
            clean_md,
            code_theme="monokai",
            hyperlinks=True
        )
        self.console.print(md)
        self.console.print()

    # -------------------------------------------------------------------------
    # 5. 步骤指示与 Token 用量状态栏 (Step Status & Token Footers)
    # -------------------------------------------------------------------------
    def render_step_status(self, step: int, max_steps: Optional[int] = None, status_text: str = ""):
        """单行轻量步骤指示，取代繁琐的 debug 日志刷屏"""
        max_str = f"/{max_steps}" if max_steps and max_steps > 0 else ""
        step_desc = f"● Step {step}{max_str}"
        if status_text:
            step_desc += f" · {status_text.strip()}"
        self.console.print(Text(f"{step_desc}...", style="dim #6b7280"))

    def render_token_usage(self, prompt_tokens: int, comp_tokens: int, total_tokens: int, model: str = ""):
        """低噪单行 Token 用量统计"""
        model_str = f" ({model})" if model else ""
        self.console.print(
            Text(f"  tokens: {prompt_tokens:,} in / {comp_tokens:,} out · total: {total_tokens:,}{model_str}\n", style="dim #6b7280")
        )

    # -------------------------------------------------------------------------
    # 6. 人机协同安全审批卡片 (Human-in-the-Loop Approval Card)
    # -------------------------------------------------------------------------
    def render_approval_prompt(self, command: str, reason: str) -> bool:
        """
        Claude Code 风格的安全审批交互卡片：
        ┌─ ⚠ Security Approval Required ────────────────────────────┐
        │ Agent requests permission to run shell command:           │
        │   git reset --hard HEAD~1                                 │
        │                                                           │
        │ Reason: Subcommand contains state-modifying operations    │
        ├───────────────────────────────────────────────────────────┤
        │ [y] Approve once                                          │
        │ [n] Reject execution                                      │
        │ [a] Trust and approve all commands in this session        │
        └───────────────────────────────────────────────────────────┘
        """
        from rich.console import Group

        warn_title = Text("[!] Security Approval Required", style="bold #fbbf24")
        msg = Text("Agent requests permission to execute terminal command:\n", style="white")

        cmd_panel = Panel(
            Text(f"  {command}", style="bold #38bdf8"),
            border_style="#fbbf24",
            padding=(0, 1),
            expand=False
        )

        reason_text = Text(f"\nReason: {reason}\n", style="dim #d1d5db")
        options_text = Text(
            "\nActions:\n"
            "  [y] - Approve once (Yes)\n"
            "  [n] - Reject and send refusal feedback (No)\n"
            "  [a] - Trust and approve all commands in this session\n",
            style="white"
        )

        panel = Panel(
            Group(msg, cmd_panel, reason_text, options_text),
            title=warn_title,
            title_align="left",
            border_style="#fbbf24",
            padding=(1, 2)
        )
        self.console.print()
        self.console.print(panel)

        while True:
            try:
                choice = input("Your choice [y/n/a] (default n): ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[dim]Action cancelled.[/dim]")
                return False

            if choice in ("y", "yes"):
                return True
            elif choice in ("n", "no", ""):
                return False
            elif choice in ("a", "all"):
                from tools.framework.policies import default_policy
                default_policy.session_approved = True
                self.console.print("[dim green][OK] Session trust granted. Subsequent commands will run automatically.[/dim green]")
                return True
            else:
                self.console.print("[red]Invalid input. Please enter y, n, or a.[/red]")

    # -------------------------------------------------------------------------
    # 7. 控制台指令美化 (Help, Status, Sessions, Projects Tables)
    # -------------------------------------------------------------------------
    def render_help(self):
        """以结构化 Rich Table 呈现控制台命令（全中文专业描述）"""
        table = Table(
            title="可用控制指令手册 (Available Slash Commands)",
            title_style="bold #34d399",
            border_style=ClaudeTheme.BORDER_DIM,
            header_style="bold #9ca3af",
            box=ROUNDED
        )
        table.add_column("控制指令", style="bold #38bdf8", no_wrap=True)
        table.add_column("分类", style="dim #9ca3af")
        table.add_column("功能说明", style="white")

        commands = [
            ("/auto", "权限模式", "切换至类似 Claude 的 AUTO 全自动免打扰执行模式"),
            ("/ask", "权限模式", "切换至敏感命令逐条人工审批模式"),
            ("/mode", "权限模式", "查看或切换当前安全审批模式 (auto / ask)"),
            ("/status, /memory", "状态排查", "查看当前 Working Memory、已读改文件与 MCP 工具挂载状态"),
            ("/history", "状态排查", "查看当前会话已完成轮次的交互摘要与 Token 消耗估算"),
            ("/undo", "执行控制", "回滚撤销上一轮对话，并将改动的源码文件自动物理还原"),
            ("/new, /reset", "会话管理", "清空内存对话历史与工作区感知，开启全新排查任务"),
            ("/restore", "会话管理", "从本地磁盘 history/ 归档目录中恢复历史会话状态"),
            ("/sessions", "会话管理", "浏览当前项目的所有会话列表及其轮次与持久化存储"),
            ("/switch <会话名>", "会话管理", "切换并激活指定会话，自动重载上下文历史快照"),
            ("/cd <路径/项目名>", "工作区", "切换当前智能体操作的目标工程工作区根目录"),
            ("/workspace", "工作区", "查看当前工程工作区根目录路径、项目归属与默认会话"),
            ("/projects", "全局索引", "查看全局已登记的工程工作区索引地图与路径清单"),
            ("/profile", "开发画像", "查看用户全局共享记忆（开发规范、编程习惯与偏好画像）"),
            ("/remember <偏好>", "开发画像", "永久记入一条跨项目通用的编码规则或开发习惯"),
            ("/forget <关键字>", "开发画像", "从全局共享记忆中移除匹配的规则偏好"),
            ("/help", "系统操作", "显示此控制指令帮助表格手册"),
            ("exit, quit", "系统操作", "安全保存并退出 Super-Harnes 智能体终端")
        ]
        for cmd, cat, desc in commands:
            table.add_row(cmd, cat, desc)

        self.console.print(table)
        self.console.print()

    def render_status_table(self, agent: Any):
        """渲染当前会话与工作区感知状态面板"""
        cm = agent.context_manager
        wm = cm.working_memory
        proj_name = getattr(agent, "project_name", getattr(getattr(agent, "session_manager", None), "project_name", "default_project"))
        active_id = getattr(getattr(agent, "session_manager", None), "active_session_id", getattr(cm, "session_id", "default"))

        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold #9ca3af", justify="right")
        table.add_column(style="white")

        table.add_row("目标工程", f"[bold cyan]{proj_name}[/]")
        table.add_row("激活会话", f"[bold magenta]{active_id}[/] [dim](第 {cm.turn_count} 轮)[/]")
        table.add_row("推理模型", f"[bold #38bdf8]{agent.model}[/]")
        table.add_row("当前目标", wm.current_goal or "[dim]未指定明确目标[/dim]")

        try:
            from tools.framework.policies import default_policy
            if default_policy.mode in ("auto", "never"):
                mode_label = "[bold green]AUTO (类似 Claude 免打扰自动执行)[/]"
            elif default_policy.session_approved:
                mode_label = "[bold green]ASK (会话已临时全部放行)[/]"
            elif default_policy.mode == "always_ask":
                mode_label = "[bold red]ALWAYS_ASK (严格逐条人工审批)[/]"
            else:
                mode_label = "[bold yellow]ASK (敏感操作交互审批)[/]"
            table.add_row("安全策略", mode_label)
        except Exception:
            pass

        table.add_row(
            "Token 预算",
            f"上限: [white]{cm.budget.total_budget}[/] | 输出预留: [white]{cm.budget.output_reserve}[/] | "
            f"API 消耗: [white]{cm.total_api_prompt_tokens:,} 输入 / {cm.total_api_completion_tokens:,} 输出[/]"
        )
        table.add_row(
            "已排查代码",
            f"[cyan]{', '.join(list(wm.inspected_files.keys()))}[/]" if wm.inspected_files else "[dim]（无）[/dim]"
        )
        table.add_row(
            "已改动文件",
            f"[yellow]{', '.join(wm.modified_files)}[/]" if wm.modified_files else "[dim]（无）[/dim]"
        )
        table.add_row(
            "挂载工具库",
            f"[green]共 {len(agent.executor.registry.get_tool_names())} 个工具[/green] "
            f"[dim](已连通 {len(agent.mcp_manager.clients)} 个外部 MCP 服务)[/dim]"
        )


        panel = Panel(
            table,
            title="● 当前工作区感知与记忆状态",
            title_align="left",
            border_style=ClaudeTheme.BORDER_DIM,
            padding=(0, 1)
        )
        self.console.print()
        self.console.print(panel)
        self.console.print()

    def render_sessions_table(self, sessions: List[Dict[str, Any]], project_name: str):
        """渲染会话管理列表"""
        table = Table(
            title=f"项目 【{project_name}】 会话管理列表",
            title_style="bold #34d399",
            border_style=ClaudeTheme.BORDER_DIM,
            box=ROUNDED
        )
        table.add_column("会话标识", style="bold cyan")
        table.add_column("状态", justify="center")
        table.add_column("已运行轮次", justify="right")
        table.add_column("改动文件数", justify="right")
        table.add_column("存储介质", style="dim")
        table.add_column("当前目标", style="white")

        for s in sessions:
            status = "[bold green]激活中[/bold green]" if s.get("is_active") else "[dim]空闲[/dim]"
            storage = "本地磁盘" if s.get("has_disk_file") else "仅内存"
            table.add_row(
                s["session_id"],
                status,
                str(s.get("turn_count", 0)),
                str(s.get("modified_files_count", 0)),
                storage,
                s.get("current_goal") or "[dim]-[/dim]"
            )
        self.console.print(table)
        self.console.print("[dim]💡 提示: 输入 [white]/switch <会话名>[/] 可随时切换并载入目标会话历史[/dim]\n")

    def render_projects_table(self, projects: List[Dict[str, Any]]):
        """渲染已登记的项目列表"""
        table = Table(
            title=f"已登记工程工作区索引地图 (共 {len(projects)} 个)",
            title_style="bold #34d399",
            border_style=ClaudeTheme.BORDER_DIM,
            box=ROUNDED
        )
        table.add_column("工程标识", style="bold cyan")
        table.add_column("工作区根目录", style="white")
        table.add_column("工程描述", style="dim")

        for p in projects:
            table.add_row(p.get("name", ""), p.get("path", ""), p.get("description", "-"))
        self.console.print(table)
        self.console.print("[dim]💡 提示: 输入 [white]/cd <工程标识>[/] 可秒级跳转至目标工程工作区[/dim]\n")

    # -------------------------------------------------------------------------
    # 8. 交互输入提示符 (Interactive Prompt: prompt_toolkit with fallback)
    # -------------------------------------------------------------------------
    def get_user_input(self, project_name: str, session_id: str) -> str:
        """
        优雅的输入交互：
        支持上下箭头翻阅历史、Tab 自动补全、底栏快捷键提示，
        在 Windows 非屏幕缓冲模式下平滑降级为 input()。
        """
        prompt_str = f"super-harnes [{project_name}:{session_id}] > "

        # 尝试使用 prompt_toolkit
        if self._prompt_session is not None:
            try:
                toolbar = "💡 Ctrl+C: 中断当前轮次 · /help: 指令手册 · Tab: 补全菜单 (支持鼠标点击/滚轮选择)"
                res = self._prompt_session.prompt(
                    prompt_str,
                    bottom_toolbar=lambda: toolbar
                )
                return res.strip()
            except Exception:
                pass

        # 降级方案
        try:
            self.console.print(f"[bold #34d399]{project_name}[/]:[magenta]{session_id}[/] [bold #38bdf8]>[/] ", end="")
            res = input().strip()
            return res
        except (KeyboardInterrupt, EOFError):
            raise


# 全局单例
default_ui = TerminalUI()
