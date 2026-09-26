# -*- coding: utf-8 -*-
"""
cli/console.py: 交互式控制台运行循环 (工业级 Claude Code 终端体验)
"""
import sys
import argparse
from core.agent import ReActAgent
from cli.commands import handle_slash_command, print_help
from tools.framework.workspace import default_workspace
from cli.ui import default_ui

def main():
    parser = argparse.ArgumentParser(description="ReAct Agent 本地终端代码助手")
    parser.add_argument("-C", "--cwd", help="指定 Agent 操作的目标工程工作区根目录", default=None)
    parser.add_argument("--plain", action="store_true", help="使用传统纯文本输出，禁用 Claude Code 富文本终端界面")
    args, _ = parser.parse_known_args()

    if not args.plain:
        default_ui.activate()

    if args.cwd:
        try:
            default_workspace.set_root(args.cwd)
        except Exception as err:
            if default_ui.is_active:
                default_ui.console.print(f"[bold red]初始化工作区失败: {err}[/bold red]")
            else:
                print(f"初始化工作区失败: {err}")
            sys.exit(1)

    try:
        agent = ReActAgent()
        active_sid = getattr(getattr(agent, "session_manager", None), "active_session_id", "default")
        proj_name = getattr(agent, "project_name", default_workspace.root.name)

        all_tools = agent.executor.registry.get_tool_names()
        mcp_tools = [name for name in all_tools if name.startswith("mcp__")]
        native_tools = [name for name in all_tools if not name.startswith("mcp__")]

        if default_ui.is_active:
            default_ui.render_banner(
                workspace_path=default_workspace.root,
                project_name=proj_name,
                session_id=active_sid,
                model=agent.model,
                native_tools=native_tools,
                mcp_tools=mcp_tools
            )
        else:
            print("正在启动 ReAct Agent 交互控制台 (本地核心 + MCP 扩展双轨版)...")
            print(f"Agent 就绪！激活模型: 【{agent.model}】")
            print(f"当前工作区根目录: 【{default_workspace.root}】")
            print(f"当前项目: 【{proj_name}】 | 当前激活会话: 【{active_sid}】")
            print(f"  [本地内置工具]: {', '.join(native_tools)}")
            print(f"  [MCP 外部工具]: {', '.join(mcp_tools) if mcp_tools else '（无）'}")
            print("💡 提示：输入 /help 查看控制指令，输入 /sessions 查看或切换会话。")

        while True:
            active_sid = getattr(getattr(agent, "session_manager", None), "active_session_id", "default")
            proj_name = getattr(agent, "project_name", default_workspace.root.name)
            try:
                if default_ui.is_active:
                    prompt = default_ui.get_user_input(proj_name, active_sid)
                else:
                    prompt = input(f"\n[{proj_name}:{active_sid}] 你: ").strip()
            except (KeyboardInterrupt, EOFError):
                if default_ui.is_active:
                    default_ui.console.print("\n[dim]Console session closed.[/dim]")
                else:
                    print("\n操作已取消，退出控制台。")
                break

            if not prompt:
                continue

            is_cmd, should_exit = handle_slash_command(agent, prompt)
            if should_exit:
                break
            if is_cmd:
                continue

            # 轮内软中断保护：执行长耗时推理或工具调用时，Ctrl+C 仅打断当前轮次，保留交互上下文与历史
            try:
                result = agent.run(prompt, verbose=True)
                if default_ui.is_active:
                    default_ui.render_assistant_response(result)
                else:
                    print(f"\nAgent 最终答复:\n{result}")
            except KeyboardInterrupt:
                if default_ui.is_active:
                    default_ui.console.print("\n[dim]● Interrupted by user. Session context preserved.[/dim]\n")
                else:
                    print("\n\n[用户中断] 已安全中止当前轮次推理与工具执行，历史会话状态已保留。")
            except Exception as err:
                if default_ui.is_active:
                    default_ui.console.print(f"\n[bold red]Execution error: {type(err).__name__}: {err}[/bold red]\n")
                else:
                    print(f"\n[运行异常] {type(err).__name__}: {err}")

    except Exception as e:
        if default_ui.is_active:
            default_ui.console.print(f"[bold red]Initialization failed: {e}[/bold red]")
        else:
            print(f"初始化失败: {e}")

if __name__ == "__main__":
    main()
