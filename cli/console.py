# -*- coding: utf-8 -*-
"""
cli/console.py: 交互式控制台运行循环
"""
import sys
from core.agent import ReActAgent
from cli.commands import handle_slash_command, print_help

def main():
    print("正在启动 ReAct Agent 交互控制台 (本地核心 + MCP 扩展双轨版)...")
    try:
        agent = ReActAgent(max_steps=10)
        print(f"Agent 就绪！激活模型: 【{agent.model}】")

        all_tools = agent.executor.registry.get_tool_names()
        mcp_tools = [name for name in all_tools if name.startswith("mcp__")]
        native_tools = [name for name in all_tools if not name.startswith("mcp__")]

        print(f"  [本地内置工具]: {', '.join(native_tools)}")
        print(f"  [MCP 外部工具]: {', '.join(mcp_tools) if mcp_tools else '（无）'}")
        print("💡 提示：输入 /help 查看控制指令。")

        while True:
            try:
                prompt = input("\n你: ").strip()
            except (KeyboardInterrupt, EOFError):
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
                print(f"\nAgent 最终答复:\n{result}")
            except KeyboardInterrupt:
                print("\n\n[用户中断] 已安全中止当前轮次推理与工具执行，历史会话状态已保留。")
            except Exception as err:
                print(f"\n[运行异常] {type(err).__name__}: {err}")

    except Exception as e:
        print(f"初始化失败: {e}")

if __name__ == "__main__":
    main()
