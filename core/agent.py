# -*- coding: utf-8 -*-
"""
core/agent.py: 具备多步推理 (Thought -> Action -> Observation) 的 ReAct 智能体核心
"""
import os
import re
import json
import atexit
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

from tools import registry
from tools.executor import ToolExecutor, default_executor
from context import ContextManager, WorkingMemory
from core.session import SessionManager
from mcp import McpManager, default_mcp_manager
from core.prompt import DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)
load_dotenv()

class ReActAgent:
    """
    具备本地核心沙箱 + MCP 外部动态扩展、安全滑动窗口与 ReAct 决策循环的智能体引擎
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_steps: Optional[int] = None,
        executor: Optional[ToolExecutor] = None,
        context_manager: Optional[ContextManager] = None,
        mcp_manager: Optional[McpManager] = None,
        session_manager: Optional[SessionManager] = None
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.model = model or os.getenv("LLM_MODEL", "deepseek-chat")
        self.system_prompt = system_prompt
        env_max_steps = int(os.getenv("AGENT_MAX_STEPS", "30"))
        self.max_steps = max_steps if max_steps is not None else env_max_steps
        self.executor = executor or default_executor
        if session_manager is not None:
            self.session_manager = session_manager
            if context_manager is not None:
                self.session_manager._sessions[context_manager.session_id] = context_manager
                self.session_manager.active_session_id = context_manager.session_id
        elif context_manager is not None:
            self.session_manager = SessionManager(default_session_id=context_manager.session_id)
            self.session_manager._sessions[context_manager.session_id] = context_manager
        else:
            self.session_manager = SessionManager(default_session_id="default")
        self.mcp_manager = mcp_manager or default_mcp_manager

        if not self.api_key or self.api_key == "your_api_key_here":
            raise ValueError("未检测到有效的 LLM_API_KEY，请检查 .env 文件！")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        # 自动挂载来自外部配置的 MCP 工具
        self.mcp_loaded = self.mcp_manager.start_and_bridge_all()
        # 退出时自动释放外部子进程
        atexit.register(self.mcp_manager.close_all)

    @property
    def context_manager(self) -> ContextManager:
        """获取当前激活会话的上下文管理器"""
        return self.session_manager.active_session

    @context_manager.setter
    def context_manager(self, mgr: ContextManager):
        """设置并注册激活会话"""
        if not hasattr(self, "session_manager") or self.session_manager is None:
            self.session_manager = SessionManager(default_session_id=mgr.session_id)
        self.session_manager._sessions[mgr.session_id] = mgr
        self.session_manager.active_session_id = mgr.session_id

    @property
    def project_name(self) -> str:
        """获取当前操作的目标项目名称"""
        return getattr(self.session_manager, "project_name", getattr(self.context_manager, "project_name", "default_project"))

    @property
    def session(self):
        """向后兼容属性"""
        return self.context_manager

    def switch_session(self, session_id: str, auto_restore: bool = True) -> ContextManager:
        """切换当前激活会话"""
        return self.session_manager.switch_session(session_id, auto_restore=auto_restore)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """获取所有可用会话列表及元数据"""
        return self.session_manager.list_sessions()

    def create_session(self, session_id: Optional[str] = None) -> ContextManager:
        """创建新会话并自动切换激活"""
        return self.session_manager.create_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        """删除指定会话及持久化文件"""
        return self.session_manager.delete_session(session_id)

    def rename_session(self, old_id: str, new_id: str) -> bool:
        """重命名会话"""
        return self.session_manager.rename_session(old_id, new_id)

    def get_session_preview(self, session_id: Optional[str] = None) -> str:
        """获取会话上下文快照与历史预览"""
        sid = session_id or self.session_manager.active_session_id
        return self.session_manager.get_session_preview(sid)

    def reset_session(self):
        """重置当前内存会话"""
        self.context_manager.clear()

    def _convert_response_to_dict(self, message: Any) -> Dict[str, Any]:
        """统一将大模型返回消息转换为纯净标准字典，杜绝数据结构异构"""
        if isinstance(message, dict):
            return message

        msg_dict: Dict[str, Any] = {
            "role": "assistant",
            "content": getattr(message, "content", "") or ""
        }
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            msg_dict["tool_calls"] = []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    msg_dict["tool_calls"].append(tc)
                else:
                    func = getattr(tc, "function", None)
                    msg_dict["tool_calls"].append({
                        "id": getattr(tc, "id", ""),
                        "type": getattr(tc, "type", "function"),
                        "function": {
                            "name": getattr(func, "name", "") if func else "",
                            "arguments": getattr(func, "arguments", "") if func else ""
                        }
                    })
        return msg_dict

    def _protect_tool_result(self, raw_content: str, max_chars: int = 35000) -> str:
        """单步工具输出保护：防止超大工具返回在轮内引发 Token 爆炸（默认放宽至 35000 字符，可完整保留数百行代码读取结果）"""
        if len(raw_content) <= max_chars:
            return raw_content
        head_len = int(max_chars * 0.7)
        tail_len = int(max_chars * 0.3)
        omitted = len(raw_content) - head_len - tail_len
        return f"{raw_content[:head_len]}\n\n...[输出过长，已保护性省略中间 {omitted} 字符]...\n\n{raw_content[-tail_len:]}"

    def _prune_inturn_observations(
        self,
        messages: List[Dict[str, Any]],
        threshold_tokens: Optional[int] = None
    ) -> int:
        """
        轮内陈旧工具观察结果折叠 (In-turn Observation Pruning):
        当轮内多步排查累积时，将 2 步以前且长度过长 (>600 字符) 的旧工具返回
        折叠为首尾片段摘要，防止多步大文件读取挤爆上下文，杜绝过早触发步间熔断。
        """
        if threshold_tokens is None:
            threshold_tokens = min(16000, int(self.context_manager.budget.total_budget * 0.4))

        current_tokens = self.context_manager.token_counter.count_messages(messages)
        if current_tokens < threshold_tokens:
            return 0

        tool_indices = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
        if len(tool_indices) <= 2:
            return 0

        earlier_indices = tool_indices[:-2]
        pruned_count = 0
        for idx in earlier_indices:
            m = messages[idx]
            content = str(m.get("content", ""))
            if len(content) > 600 and "[历史观察结果已由 Agent 消化" not in content:
                head = content[:200].strip()
                tail = content[-100:].strip()
                omitted = len(content) - len(head) - len(tail)
                pruned_text = (
                    f"{head}\n\n"
                    f"...[历史观察结果已由 Agent 消化，正文已折叠 (省略 {omitted} 字符) 以节约上下文]...\n\n"
                    f"{tail}"
                )
                m["content"] = pruned_text
                if self.context_manager.current_turn:
                    t_id = m.get("tool_call_id")
                    for cm in self.context_manager.current_turn.messages:
                        if cm.get("role") == "tool" and cm.get("tool_call_id") == t_id:
                            cm["content"] = pruned_text
                            break
                pruned_count += 1
        return pruned_count


    def run(self, user_prompt: str, verbose: bool = True) -> str:
        """
        运行 ReAct 核心循环：
        具备轮内预算防爆炸、消息格式归一化、工作记忆轮内即时同步与事务性保护
        """
        tools_schema = self.executor.registry.get_schemas()
        tools_json = json.dumps(tools_schema, ensure_ascii=False) if tools_schema else ""
        tools_tokens = self.context_manager.token_counter.count_text(tools_json)

        # 开启新原子轮次
        self.context_manager.start_new_turn(user_prompt)

        # 组装安全上下文
        messages, metrics = self.context_manager.build_context_with_watermark(
            self.system_prompt,
            client=self.client,
            model=self.model,
            tools_tokens=tools_tokens
        )

        if verbose:
            zone_desc = f"{metrics['zone']} ({metrics['raw_utilization']*100:.1f}%)"
            gate_desc = " [已触发硬门禁截断]" if metrics.get("hard_gatekeeper_triggered") else ""
            print(f"\n{'='*20} 轮次 #{self.context_manager.turn_count} [水位: {zone_desc}{gate_desc}] | 引擎: {self.model} {'='*20}")
            print(f"用户目标: {user_prompt}\n")

        output_reserve = self.context_manager.budget.output_reserve
        turn_finished = False

        try:
            for step in range(1, self.max_steps + 1):
                remaining_steps = self.max_steps - step
                is_last_step = (step == self.max_steps)
                is_near_end = (remaining_steps <= 2 and self.max_steps > 3)

                # 0. 轮内陈旧工具观察结果折叠 (In-turn Observation Pruning)
                if step > 2:
                    pruned_obs = self._prune_inturn_observations(messages)
                    if pruned_obs > 0 and verbose:
                        print(f"  [观察结果裁剪] 已折叠 {pruned_obs} 条早期历史工具长输出，释放轮内上下文空间。")

                # 1. 轮内步间动态 Token 预算核验与步间熔断（高优先级）
                current_context_tokens = self.context_manager.token_counter.count_messages(messages)
                max_context_allowed = self.context_manager.budget.total_budget - output_reserve - tools_tokens
                if step > 1 and current_context_tokens > max_context_allowed:
                    circuit_msg = (
                        f"【系统保护】轮内多步推理消耗已达上下文上限 ({current_context_tokens}/{self.context_manager.budget.total_budget} Tokens)，"
                        f"为避免触发大模型长度超限异常 (400 context_length_exceeded)，已安全熔断并终止后续工具调用。"
                    )
                    logger.warning(
                        f"轮内多步推理触发动态预算熔断: Step {step} 上下文 Tokens ({current_context_tokens}) > 允许上限 ({max_context_allowed})。"
                    )
                    if verbose:
                        print(f"\n[动态熔断] {circuit_msg}")
                    self.context_manager.add_assistant_message(circuit_msg)
                    self.context_manager.finish_current_turn()
                    turn_finished = True
                    return circuit_msg

                if verbose:
                    step_status = f" (剩余 {remaining_steps} 步)" if not is_last_step else " (最终步收尾)"
                    print(f"[Step {step}/{self.max_steps}] Agent 正在思考{step_status}...")

                # 2. 最终步平滑收拢机制 (Graceful Wrap-up):
                # 到达最后一步时，关闭工具调用强制模型基于已收集的所有事实向用户输出最终答复，绝不机械崩溃
                call_tools = tools_schema if (tools_schema and not is_last_step) else None
                call_tool_choice = "auto" if call_tools else None

                # 3. 动态注入步数进度与倒计时警示 (注入在当前轮 User 消息动态尾部，保全头部缓存)
                step_banner = f"[当前执行进度: 第 {step}/{self.max_steps} 步 | 剩余 {remaining_steps} 步]"
                if is_last_step:
                    step_banner += " [重要提醒: 本轮已达最终步，工具调用已关闭。请基于上述已排查掌握的全部代码与事实，向用户输出详尽完整的最终分析答复或改动说明]"
                elif is_near_end:
                    step_banner += " [提示: 步数即将耗尽，请尽快收拢排查，准备输出结论]"

                updated_banner = False
                for m in messages:
                    if m.get("role") == "user" and "[用户当前提问]:" in str(m.get("content", "")):
                        c_text = str(m.get("content", ""))
                        c_clean = re.sub(r"\n*\[当前执行进度:.*?\]\n*", "\n", c_text).strip()
                        parts = c_clean.split("[用户当前提问]:", 1)
                        u_pre = parts[0].strip()
                        u_suf = parts[1].strip() if len(parts) > 1 else ""
                        m["content"] = f"{u_pre}\n\n{step_banner}\n\n[用户当前提问]: {u_suf}"
                        updated_banner = True
                        break
                if not updated_banner:
                    for m in reversed(messages):
                        if m.get("role") == "user":
                            old_c = str(m.get("content", ""))
                            old_c = re.sub(r"\n*\[当前执行进度:.*?\]\n*", "\n", old_c).strip()
                            m["content"] = f"{step_banner}\n\n{old_c}"
                            break

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=call_tools,
                    tool_choice=call_tool_choice,
                    max_tokens=output_reserve
                )

                # 捕获大模型权威真实 API Usage 反馈并记录校准
                usage = getattr(response, "usage", None)
                if usage:
                    prompt_toks = getattr(usage, "prompt_tokens", 0) or 0
                    comp_toks = getattr(usage, "completion_tokens", 0) or 0
                    total_toks = getattr(usage, "total_tokens", prompt_toks + comp_toks) or (prompt_toks + comp_toks)
                    self.context_manager.record_api_usage(prompt_toks, comp_toks)
                    if verbose:
                        print(f"  [API 实际用量] 输入: {prompt_toks} Tokens | 输出: {comp_toks} Tokens | 计费总计: {total_toks} Tokens")

                response_msg = response.choices[0].message
                assistant_dict = self._convert_response_to_dict(response_msg)

                if assistant_dict.get("tool_calls"):
                    messages.append(assistant_dict)
                    self.context_manager.add_assistant_message(assistant_dict)

                    if assistant_dict.get("content") and verbose:
                        print(f"  [Thought] {assistant_dict['content']}")

                    # 调度执行工具
                    tool_results = self.executor.execute_tool_calls(
                        response_msg.tool_calls,
                        verbose=verbose
                    )

                    # 单步工具输出保护
                    protected_results = []
                    for tr in tool_results:
                        safe_content = self._protect_tool_result(str(tr.get("content", "")))
                        protected_results.append({
                            "role": "tool",
                            "tool_call_id": tr.get("tool_call_id", ""),
                            "content": safe_content
                        })

                    messages.extend(protected_results)

                    # 观察阶段：更新工作区感知状态
                    for tc in assistant_dict["tool_calls"]:
                        fname = tc["function"]["name"]
                        raw_args = tc["function"]["arguments"]
                        matched_res = next((tr["content"] for tr in tool_results if tr["tool_call_id"] == tc["id"]), "")
                        try:
                            args_dict = json.loads(raw_args) if raw_args else {}
                        except Exception:
                            args_dict = {}
                        self.context_manager.update_from_tool(
                            fname,
                            args_dict,
                            matched_res,
                            turn_id=self.context_manager.turn_count
                        )

                    # 轮内严格单调追加 (Strict Append-Only) 与 Prompt Cache 保障：
                    # 轮内已包含最新 Tool Call 与 Tool Result 明文，无需也不得回溯篡改前序 User 消息，
                    # 确保 Step 1 -> Step N 全程前缀逐字一致，100% 稳态命中大模型 KV Cache！
                    # 工作记忆状态已在 Python 内存中精确维护，将在 finish_current_turn 时原子落盘并在下一轮生效。
                    self.context_manager.add_tool_results(protected_results)
                else:
                    if verbose:
                        if is_last_step:
                            print(f"\n[平滑收尾] Agent 在最终步 (第 {step} 步) 成功汇总事实并完成解答。")
                        else:
                            print(f"\n[任务达成] Agent 在第 {step} 步完成了本轮推理。")

                    final_text = assistant_dict.get("content") or "（无返回内容）"
                    self.context_manager.add_assistant_message(assistant_dict)
                    self.context_manager.finish_current_turn()
                    turn_finished = True
                    return final_text

            fallback_msg = f"已完成本轮 {self.max_steps} 步工程排查与推理。"
            wm = self.context_manager.working_memory
            if wm.inspected_files:
                fallback_msg += f" 已排查代码: {list(wm.inspected_files.keys())}。"
            if wm.modified_files:
                fallback_msg += f" 已修改文件: {wm.modified_files}。"
            if verbose:
                print(f"\n[优雅收尾] {fallback_msg}")
            self.context_manager.add_assistant_message(fallback_msg)
            self.context_manager.finish_current_turn()
            turn_finished = True
            return fallback_msg

        finally:
            # 关键修复：中断或异常时安全撤销，绝不调用 finish_current_turn 打上假完成标记
            if not turn_finished and self.context_manager.current_turn:
                logger.warning("轮次未正常完成即退出，安全取消当前悬挂轮次。")
                self.context_manager.abort_current_turn()
