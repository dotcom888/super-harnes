# -*- coding: utf-8 -*-
import re
from typing import List, Dict, Any, Optional
from openai.types.chat import ChatCompletionMessage

class WorkingMemory:
    """
    工作区状态记忆 (Working Memory):
    显式维护代码排查过程中的状态与元信息，
    防止多轮对话中因历史消息过长被折叠而遗忘关键排查上下文。
    """
    def __init__(self):
        self.current_goal: str = ""
        self.inspected_files: Dict[str, str] = {}  # {filepath: "第 1-100 行"}
        self.modified_files: List[str] = []         # [filepath]
        self.last_test_status: Optional[str] = None # 最近一次命令执行结果摘要

    def update_goal(self, goal: str):
        if goal and goal.strip():
            self.current_goal = goal.strip()

    def update_from_tool(self, tool_name: str, args: Dict[str, Any], result: str):
        """根据工具执行结果自动感知并刷新工作区状态"""
        # 1. 文件读取感知
        if tool_name == "read_file":
            filepath = args.get("file_path", "")
            start = args.get("start_line", 1)
            max_lines = args.get("max_lines", 100)
            if filepath:
                self.inspected_files[filepath] = f"第 {start} 至 {int(start) + int(max_lines) - 1} 行"

        # 2. 补丁修改感知
        elif tool_name == "apply_patch":
            patch_content = args.get("patch_content", "")
            created = re.findall(r"\*\*\*\s*Create File:\s*([^\n]+)", patch_content)
            updated = re.findall(r"\*\*\*\s*Update File:\s*([^\n]+)", patch_content)
            for f in created + updated:
                f_clean = f.strip()
                if f_clean not in self.modified_files:
                    self.modified_files.append(f_clean)

        # 3. 终端执行/测试感知
        elif tool_name == "run_shell":
            cmd = args.get("command", "")
            first_line = result.splitlines()[0] if result else ""
            status = first_line if "执行状态" in first_line else "已执行"
            self.last_test_status = f"`{cmd}` -> {status}"

    def format_prompt_context(self) -> str:
        """格式化为结构化提示词，动态注入到 Agent 的系统上下文中"""
        sections = []
        if self.current_goal:
            sections.append(f"- **当前协同目标**: {self.current_goal}")
        
        if self.inspected_files:
            files_desc = ", ".join([f"`{f}` ({info})" for f, info in list(self.inspected_files.items())[-8:]])
            sections.append(f"- **已排查代码**: {files_desc}")
            
        if self.modified_files:
            mod_desc = ", ".join([f"`{f}`" for f in self.modified_files[-8:]])
            sections.append(f"- **已修改文件**: {mod_desc}")

        if self.last_test_status:
            sections.append(f"- **最新验证状态**: {self.last_test_status}")

        if not sections:
            return ""

        return "\n\n【当前工作区感知状态 (Working Memory)】:\n" + "\n".join(sections)

    def clear(self):
        self.current_goal = ""
        self.inspected_files.clear()
        self.modified_files.clear()
        self.last_test_status = None


class Session:
    """
    会话管理器 (Session):
    负责多轮对话消息序列的持久化、OpenAI 协议一致性维护与长历史智能剪枝。
    """
    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.messages: List[Dict[str, Any]] = []
        self.working_memory = WorkingMemory()
        self.turn_count: int = 0

    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})
        self.turn_count += 1
        # 如果尚未指定目标，以首轮提示作为默认目标
        if not self.working_memory.current_goal:
            self.working_memory.update_goal(content[:100])

    def add_assistant_message(self, message: Any):
        """
        添加助手消息（兼容量产 ChatCompletionMessage 对象与标准 Dict）
        """
        if isinstance(message, ChatCompletionMessage):
            msg_dict: Dict[str, Any] = {"role": "assistant", "content": message.content or ""}
            if message.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            self.messages.append(msg_dict)
        elif isinstance(message, dict):
            self.messages.append(message)
        else:
            # 兼容模型直接返回文本
            self.messages.append({"role": "assistant", "content": str(message)})

    def add_tool_results(self, tool_results: List[Dict[str, Any]]):
        """添加工具执行响应消息"""
        for item in tool_results:
            self.messages.append({
                "role": "tool",
                "tool_call_id": item.get("tool_call_id", ""),
                "content": str(item.get("content", ""))
            })

    def compact_history(self, max_observation_chars: int = 500):
        """
        安全历史剪枝：
        将早期历史轮次中过长的数据/代码观察（Tool Observation）进行压缩折叠，
        同时严格保留 role: 'tool' 和 tool_call_id，杜绝 OpenAI 协议报错。
        """
        # 找到最后一个 user 消息的索引，只对该索引之前的历史轮次进行压缩
        last_user_idx = -1
        for idx in range(len(self.messages) - 1, -1, -1):
            if self.messages[idx].get("role") == "user":
                last_user_idx = idx
                break

        if last_user_idx <= 0:
            return

        for i in range(last_user_idx):
            msg = self.messages[i]
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                if len(content) > max_observation_chars:
                    head = content[:150]
                    tail = content[-100:]
                    msg["content"] = (
                        f"{head}\n\n"
                        f"... [历史详细日志已折叠（省略 {len(content) - 250} 字符），关键信息已沉淀至工作区记忆] ...\n\n"
                        f"{tail}"
                    )

    def rollback_last_turn(self) -> bool:
        """
        回滚上一轮对话（从最后一条 user 消息起到末尾的所有消息）
        """
        last_user_idx = -1
        for idx in range(len(self.messages) - 1, -1, -1):
            if self.messages[idx].get("role") == "user":
                last_user_idx = idx
                break

        if last_user_idx == -1:
            return False

        self.messages = self.messages[:last_user_idx]
        self.turn_count = max(0, self.turn_count - 1)
        return True

    def build_messages(self, base_system_prompt: str) -> List[Dict[str, Any]]:
        """
        动态组装给大模型的完整上下文序列：
        Base System Prompt + Working Memory 注入 + 完整/剪枝后的会话历史
        """
        working_context = self.working_memory.format_prompt_context()
        full_system = base_system_prompt
        if working_context:
            full_system += working_context

        full_messages = [{"role": "system", "content": full_system}]
        full_messages.extend(self.messages)
        return full_messages

    def clear(self):
        """清空会话"""
        self.messages.clear()
        self.working_memory.clear()
        self.turn_count = 0
