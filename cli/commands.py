# -*- coding: utf-8 -*-
"""
cli/commands.py: 控制台斜杠命令 (/status, /restore, /undo, /reset 等) 处理分发器
"""
from typing import Tuple

HELP_TEXT = """
可用控制指令：
  /status, /memory  - 查看当前 Working Memory 与 MCP 工具挂载状态
  /restore          - 从磁盘 history/ 目录恢复历史会话
  /undo             - 回滚上一轮对话历史
  /new, /reset      - 清空内存会话记忆，开启全新排查任务
  /history          - 查看会话历史简报
  /help             - 显示此帮助信息
  quit, exit        - 退出程序
"""

def print_help():
    print(HELP_TEXT)

def handle_slash_command(agent, prompt: str) -> Tuple[bool, bool]:
    """
    处理斜杠命令。
    :return: (is_command, should_exit)
    """
    cmd_lower = prompt.strip().lower()

    if cmd_lower in ["quit", "exit"]:
        print("再见！")
        return True, True

    if cmd_lower in ["/new", "/clear", "/reset"]:
        agent.reset_session()
        print("【会话已重置】内存对话历史与工作区感知已清空。")
        return True, False

    if cmd_lower == "/restore":
        if agent.context_manager.restore_from_disk():
            print(f"【恢复成功】已从本地磁盘恢复共 {agent.context_manager.turn_count} 轮历史！")
        else:
            print("【恢复失败】未找到有效的历史归档文件。")
        return True, False

    if cmd_lower in ["/status", "/memory"]:
        wm = agent.context_manager.working_memory
        print("\n" + "="*20 + " 当前工作区感知与工具状态 " + "="*20)
        print(f"当前模型: {agent.model}")
        print(f"当前轮次: {agent.context_manager.turn_count}")
        print(f"当前目标: {wm.current_goal or '（未指定）'}")
        cm = agent.context_manager
        print(f"当前 Token 预算: 上限 {cm.budget.total_budget} | 输出预留 {cm.budget.output_reserve}")
        print(f"累计 API 消耗: 输入 {cm.total_api_prompt_tokens} Tokens | 输出 {cm.total_api_completion_tokens} Tokens")
        print(f"已读文件: {list(wm.inspected_files.keys()) or '（无）'}")
        print(f"已改文件: {wm.modified_files or '（无）'}")
        print(f"已挂载 MCP 服务: {list(agent.mcp_manager.clients.keys())}")
        print(f"全量可用工具数: {len(agent.executor.registry.get_tool_names())} 个")
        print("="*60)
        return True, False

    if cmd_lower == "/undo":
        if agent.context_manager.rollback_last_turn():
            restored = getattr(agent.context_manager, "last_rolled_back_files", [])
            if restored:
                print("【回滚成功】已撤销上一轮对话，并已将以下文件还原至改动前状态：")
                for f_info in restored:
                    print(f"  • {f_info}")
            else:
                print("【回滚成功】已撤销上一轮对话交互（本轮未改动物理磁盘代码）。")
        else:
            print("【回滚失败】当前会话没有可回滚的轮次。")
        return True, False

    if cmd_lower == "/history":
        print("\n" + "="*20 + " 会话历史摘要 " + "="*20)
        if not agent.context_manager.completed_turns:
            print("（当前暂无已完成的轮次）")
        for chunk in agent.context_manager.completed_turns:
            user_text = chunk.messages[0].get("content", "") if chunk.messages else ""
            print(f"[轮次 #{chunk.turn_id}] 用户: {user_text[:60]}")
            print(f"             消息条数: {len(chunk.messages)} 条, 预估 Token: ~{chunk.estimate_tokens(agent.context_manager.token_counter)}")
        print("="*54)
        return True, False

    if cmd_lower == "/help":
        print_help()
        return True, False

    return False, False
