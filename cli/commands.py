# -*- coding: utf-8 -*-
"""
cli/commands.py: 控制台斜杠命令 (/status, /sessions, /switch, /undo, /reset 等) 处理分发器
"""
import shlex
from typing import Tuple

HELP_TEXT = """
可用控制指令：
  /status, /memory         - 查看当前 Working Memory 与 MCP 工具挂载状态
  /restore                 - 从磁盘 history/ 目录恢复历史会话
  /undo                    - 回滚上一轮对话历史
  /new, /reset             - 清空当前内存会话记忆，开启全新排查任务
  /history                 - 查看当前会话历史简报
  /cd <路径>, /workspace   - 切换或查看目标工程工作区根目录
  /profile                 - 查看用户全局共享记忆（开发规范与偏好画像）
  /remember <偏好>         - 永久记入一条全局编码偏好或开发习惯
  /forget <关键字>         - 从全局记忆中移除匹配的偏好
  /projects                - 查看所有已登记的工程工作区索引地图
  /sessions, /session list - 查看所有会话列表及当前激活会话
  /switch <name>           - 切换到指定会话（自动载入历史并显示上下文快照）
  /session new <名>        - 创建并激活全新会话
  /session delete <名>     - 删除指定会话及其磁盘归档
  /session rename <旧> <新>- 重命名会话
  /session info [名]       - 查看指定或当前会话的上下文快照
  /help                    - 显示此帮助信息
  quit, exit               - 退出程序
"""

def print_help():
    try:
        from cli.ui import default_ui
        if default_ui.is_active:
            default_ui.render_help()
            return
    except Exception:
        pass
    print(HELP_TEXT)

def handle_slash_command(agent, prompt: str) -> Tuple[bool, bool]:
    """
    处理斜杠命令。
    :return: (is_command, should_exit)
    """
    raw_prompt = prompt.strip()
    cmd_lower = raw_prompt.lower()

    if cmd_lower in ["quit", "exit"]:
        print("再见！")
        return True, True

    # 动态切换或查看工作区：/cd <path> 或 /workspace [path]
    if cmd_lower in ["/workspace", "/cd"]:
        from tools.framework.workspace import default_workspace
        proj_name = getattr(agent, "project_name", default_workspace.root.name)
        active_id = getattr(getattr(agent, "session_manager", None), "active_session_id", "default")
        print(f"当前工作区根目录: 【{default_workspace.root}】 | 当前项目: 【{proj_name}】 | 当前会话: 【{active_id}】")
        print("💡 提示: 输入 /cd <目标路径> 或 /workspace <目标路径> 可直接切换到其他项目工程。")
        return True, False

    if cmd_lower.startswith("/cd ") or cmd_lower.startswith("/workspace "):
        parts = raw_prompt.split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            from tools.framework.workspace import default_workspace
            print(f"当前工作区根目录: 【{default_workspace.root}】")
            return True, False
        raw_target = parts[1].strip()
        from context.global_memory import default_global_memory
        from pathlib import Path
        # 智能项目名解析：若输入的不是现有路径，支持直接通过已登记工程名快速跳转
        reg_info = default_global_memory.get_project(raw_target)
        if reg_info and not Path(raw_target).exists():
            target_path = reg_info["path"]
            print(f"💡 匹配到已登记项目 【{reg_info['name']}】，目标路径: {target_path}")
        else:
            target_path = raw_target

        try:
            if hasattr(agent, "switch_workspace"):
                new_root = agent.switch_workspace(target_path)
            else:
                from tools.framework.workspace import default_workspace
                new_root = default_workspace.set_root(target_path)
            proj_name = getattr(agent, "project_name", new_root.name)
            active_id = getattr(getattr(agent, "session_manager", None), "active_session_id", "default")
            print("【工作区切换成功】")
            print(f"  • 目标工作区根目录: 【{new_root}】")
            print(f"  • 激活项目名称: 【{proj_name}】")
            print(f"  • 激活默认会话: 【{active_id}】（历史日志独立归档于 history/{proj_name}/）")
        except Exception as e:
            print(f"【切换工作区失败】{e}")
        return True, False

    # 用户全局记忆查看指令：/profile, /user
    if cmd_lower in ["/profile", "/user", "/profile show"]:
        from context.global_memory import default_global_memory
        print(default_global_memory.format_profile_view())
        return True, False

    # 永久记入全局习惯：/remember <习惯内容>
    if cmd_lower.startswith("/remember"):
        parts = raw_prompt.split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            from context.global_memory import default_global_memory
            print(default_global_memory.format_profile_view())
            return True, False
        habit_text = parts[1].strip()
        from context.global_memory import default_global_memory
        if default_global_memory.add_habit(habit_text):
            print(f"【全局记忆已更新】已成功记入偏好规范：\n  • {habit_text}")
            print("💡 该偏好已永久保存至 ~/.super-harnes/global_memory.json，跨所有工程与会话生效。")
        else:
            print("【提示】该偏好此前已登记，无需重复添加。")
        return True, False

    # 移除全局习惯：/forget <关键字>
    if cmd_lower.startswith("/forget"):
        parts = raw_prompt.split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            print("【参数缺失】请指定要遗忘的偏好关键字，例如: /forget 类型注解")
            return True, False
        kw = parts[1].strip()
        from context.global_memory import default_global_memory
        removed = default_global_memory.remove_habit(kw)
        if removed:
            print(f"【全局记忆已更新】已移除以下 {len(removed)} 条偏好：")
            for r in removed:
                print(f"  • {r}")
        else:
            print(f"【提示】未找到匹配关键字 '{kw}' 的偏好。")
        return True, False

    # 查看所有已登记工程：/projects
    if cmd_lower in ["/projects", "/project list", "/projects list"]:
        from context.global_memory import default_global_memory
        projs = default_global_memory.list_projects()
        try:
            from cli.ui import default_ui
            if default_ui.is_active:
                default_ui.render_projects_table(projs)
                return True, False
        except Exception:
            pass
        print("\n" + "="*20 + f" 已登记工程工作区地图 (共 {len(projs)} 个) " + "="*20)
        for p in projs:
            print(f"  • 【{p['name']}】: {p['path']}")
            if p.get("description"):
                print(f"      简介: {p['description']}")
        print("="*66)
        print("💡 提示: 输入 /cd <工程名> 可直接根据名称秒级跳转目标工程。")
        return True, False

    if cmd_lower in ["/new", "/clear", "/reset"]:
        if hasattr(agent, "reset_session"):
            agent.reset_session()
        else:
            agent.context_manager.clear()
        print("【会话已重置】内存对话历史与工作区感知已清空。")
        return True, False

    # 支持 /new <session_name> 快速创建并切换新会话
    if cmd_lower.startswith("/new ") or cmd_lower.startswith("/reset "):
        parts = raw_prompt.split(None, 1)
        if len(parts) > 1 and parts[1].strip():
            new_name = parts[1].strip()
            if hasattr(agent, "create_session"):
                mgr = agent.create_session(new_name)
                active_id = getattr(getattr(agent, "session_manager", None), "active_session_id", getattr(mgr, "session_id", new_name))
                print(f"【新建会话】已成功创建并激活新会话: 【{active_id}】（全新空白上下文）")
            else:
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
        try:
            from cli.ui import default_ui
            if default_ui.is_active:
                default_ui.render_status_table(agent)
                return True, False
        except Exception:
            pass

        wm = agent.context_manager.working_memory
        print("\n" + "="*20 + " 当前工作区感知与工具状态 " + "="*20)
        proj_name = getattr(agent, "project_name", getattr(getattr(agent, "session_manager", None), "project_name", "default_project"))
        active_id = getattr(getattr(agent, "session_manager", None), "active_session_id", getattr(agent.context_manager, "session_id", "default"))
        print(f"当前项目: 【{proj_name}】")
        print(f"当前会话: 【{active_id}】")
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
        active_id = getattr(getattr(agent, "session_manager", None), "active_session_id", getattr(agent.context_manager, "session_id", "default"))
        print("\n" + "="*20 + f" 会话 【{active_id}】 历史摘要 " + "="*20)
        if not agent.context_manager.completed_turns:
            print("（当前暂无已完成的轮次）")
        for chunk in agent.context_manager.completed_turns:
            user_text = chunk.messages[0].get("content", "") if chunk.messages else ""
            print(f"[轮次 #{chunk.turn_id}] 用户: {user_text[:60]}")
            print(f"             消息条数: {len(chunk.messages)} 条, 预估 Token: ~{chunk.estimate_tokens(agent.context_manager.token_counter)}")
        print("="*54)
        return True, False

    # 多会话列出指令：/sessions 或 /session list 或 /session
    if cmd_lower in ["/sessions", "/session", "/session list"]:
        if hasattr(agent, "list_sessions"):
            sessions = agent.list_sessions()
        elif hasattr(getattr(agent, "session_manager", None), "list_sessions"):
            sessions = agent.session_manager.list_sessions()
        else:
            sessions = []

        proj_name = getattr(agent, "project_name", getattr(getattr(agent, "session_manager", None), "project_name", "default_project"))
        try:
            from cli.ui import default_ui
            if default_ui.is_active:
                default_ui.render_sessions_table(sessions, proj_name)
                return True, False
        except Exception:
            pass
        print("\n" + "="*20 + f" 项目 【{proj_name}】 会话列表 (共 {len(sessions)} 个) " + "="*20)
        for s in sessions:
            prefix = " * " if s.get("is_active") else "   "
            active_tag = "【当前激活】" if s.get("is_active") else ""
            disk_tag = "已存盘" if s.get("has_disk_file") else "全新/未落盘"
            print(f"{prefix}{s['session_id']:<15} {active_tag:<8} | 轮次: {s['turn_count']:<2} | 已改文件: {s['modified_files_count']:<2} | 存储: {disk_tag:<9} | 目标: {s['current_goal']}")
        print("="*60)
        print("💡 提示: 输入 /switch <会话名> 切换会话，输入 /session new <会话名> 创建新会话。")
        return True, False

    # 快捷切换指令：/switch <session_id>
    if cmd_lower.startswith("/switch"):
        parts = raw_prompt.split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            print("【参数缺失】请提供目标会话名称，例如: /switch bugfix")
            return True, False
        target_sid = parts[1].strip()
        try:
            if hasattr(agent, "switch_session"):
                agent.switch_session(target_sid, auto_restore=True)
            elif hasattr(getattr(agent, "session_manager", None), "switch_session"):
                agent.session_manager.switch_session(target_sid, auto_restore=True)
            active_id = getattr(getattr(agent, "session_manager", None), "active_session_id", target_sid)
            print(f"【会话切换成功】当前激活会话: 【{active_id}】")
            if hasattr(agent, "get_session_preview"):
                print(agent.get_session_preview(active_id))
            elif hasattr(getattr(agent, "session_manager", None), "get_session_preview"):
                print(agent.session_manager.get_session_preview(active_id))
            print("💡 提示：该会话历史已就绪，你的下一条提问将直接进入该会话（无需手动输入 /restore）。")
        except Exception as e:
            print(f"【切换失败】{e}")
        return True, False

    # 复合会话管理指令：/session <subcommand> [...]
    if cmd_lower.startswith("/session "):
        try:
            tokens = shlex.split(raw_prompt)
        except Exception:
            tokens = raw_prompt.split()

        subcmd = tokens[1].lower() if len(tokens) > 1 else "list"

        if subcmd in ["list", "ls"]:
            sessions = agent.list_sessions() if hasattr(agent, "list_sessions") else []
            print("\n" + "="*20 + f" 会话列表 (共 {len(sessions)} 个) " + "="*20)
            for s in sessions:
                prefix = " * " if s.get("is_active") else "   "
                active_tag = "【当前激活】" if s.get("is_active") else ""
                disk_tag = "已存盘" if s.get("has_disk_file") else "全新/未落盘"
                print(f"{prefix}{s['session_id']:<15} {active_tag:<8} | 轮次: {s['turn_count']:<2} | 已改文件: {s['modified_files_count']:<2} | 存储: {disk_tag:<9} | 目标: {s['current_goal']}")
            print("="*60)
            return True, False

        if subcmd in ["switch", "use"]:
            if len(tokens) < 3 or not tokens[2].strip():
                print("【参数缺失】请提供目标会话名称，例如: /session switch bugfix")
                return True, False
            target_sid = tokens[2].strip()
            try:
                agent.switch_session(target_sid, auto_restore=True)
                active_id = getattr(getattr(agent, "session_manager", None), "active_session_id", target_sid)
                print(f"【会话切换成功】当前激活会话: 【{active_id}】")
                if hasattr(agent, "get_session_preview"):
                    print(agent.get_session_preview(active_id))
                print("💡 提示：该会话历史已就绪，你的下一条提问将直接进入该会话（无需手动输入 /restore）。")
            except Exception as e:
                print(f"【切换失败】{e}")
            return True, False

        if subcmd in ["new", "create", "add"]:
            name = tokens[2].strip() if len(tokens) > 2 else None
            try:
                mgr = agent.create_session(name)
                active_id = getattr(getattr(agent, "session_manager", None), "active_session_id", getattr(mgr, "session_id", name))
                print(f"【新建会话成功】已创建并激活新会话: 【{active_id}】（全新空白上下文）")
            except Exception as e:
                print(f"【创建失败】{e}")
            return True, False

        if subcmd in ["delete", "remove", "rm"]:
            if len(tokens) < 3 or not tokens[2].strip():
                print("【参数缺失】请提供要删除的会话名称，例如: /session delete bugfix")
                return True, False
            target_sid = tokens[2].strip()
            try:
                if agent.delete_session(target_sid):
                    active_id = getattr(getattr(agent, "session_manager", None), "active_session_id", "default")
                    print(f"【删除成功】已移除会话: 【{target_sid}】及其磁盘归档（当前激活会话: 【{active_id}】）。")
                else:
                    print(f"【删除失败】无法删除会话: 【{target_sid}】")
            except Exception as e:
                print(f"【删除失败】{e}")
            return True, False

        if subcmd in ["rename", "mv"]:
            if len(tokens) < 4:
                print("【参数缺失】格式: /session rename <旧会话名> <新会话名>")
                return True, False
            old_name = tokens[2].strip()
            new_name = tokens[3].strip()
            try:
                if agent.rename_session(old_name, new_name):
                    active_id = getattr(getattr(agent, "session_manager", None), "active_session_id", new_name)
                    print(f"【重命名成功】会话 【{old_name}】 已更名为 【{new_name}】（当前激活: 【{active_id}】）。")
                else:
                    print(f"【重命名失败】原会话不存在或新名称无效。")
            except Exception as e:
                print(f"【重命名失败】{e}")
            return True, False

        if subcmd in ["info", "preview", "show"]:
            sid = tokens[2].strip() if len(tokens) > 2 else getattr(getattr(agent, "session_manager", None), "active_session_id", "default")
            if hasattr(agent, "get_session_preview"):
                print(agent.get_session_preview(sid))
            return True, False

        print(f"【未知子命令】/session {subcmd}，输入 /help 查看用法。")
        return True, False

    if cmd_lower == "/help":
        print_help()
        return True, False

    return False, False
