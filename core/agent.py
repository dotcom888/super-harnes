# -*- coding: utf-8 -*-
"""
core/agent.py: 具备多步推理 (Thought -> Action -> Observation) 的 ReAct 智能体核心
"""
import os
import re
import json
import atexit
import logging
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

from tools import registry
from tools.executor import ToolExecutor, default_executor
from tools.framework.output_clamp import clamp_generic_output, get_dynamic_max_chars
from context import ContextManager, WorkingMemory
from core.session import SessionManager
from core.loop_detector import LoopDetector, LoopState
from core.stage_manager import StageManager, TaskStage
from mcp import McpManager, default_mcp_manager
from core.prompt import DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)
load_dotenv()
_agent_env = Path(__file__).resolve().parent.parent / ".env"
if _agent_env.exists():
    load_dotenv(dotenv_path=_agent_env)

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
        self._custom_system_prompt: Optional[str] = system_prompt if system_prompt != DEFAULT_SYSTEM_PROMPT else None
        env_max_steps = int(os.getenv("AGENT_MAX_STEPS", "0"))
        self.max_steps = max_steps if max_steps is not None else env_max_steps
        self.loop_detector = LoopDetector()
        self.stage_manager = StageManager(enable_stage_masking=False)
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
    def system_prompt(self) -> str:
        if self._custom_system_prompt is not None:
            return self._custom_system_prompt
        from core.prompt import build_system_prompt
        return build_system_prompt()

    @system_prompt.setter
    def system_prompt(self, val: Optional[str]):
        if val == DEFAULT_SYSTEM_PROMPT:
            self._custom_system_prompt = None
        else:
            self._custom_system_prompt = val

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

    def switch_workspace(self, workspace_path: Union[str, Path]) -> Path:
        """动态切换目标工程工作区根目录并重载项目级会话管理器"""
        from tools.framework.workspace import default_workspace
        new_root = default_workspace.set_root(workspace_path)
        self.session_manager = SessionManager(
            default_session_id="default",
            workspace=default_workspace,
            project_name=new_root.name
        )
        return new_root

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

    def _protect_tool_result(
        self,
        raw_content: str,
        max_chars: Optional[int] = None,
        zone: Optional[str] = None,
        tool_name: str = "tool"
    ) -> str:
        """
        单步工具输出保护：防止超大工具返回在轮内引发 Token 爆炸。
        具备多级语义提取、动态上下文水位联动与全量溢出落盘追查透镜。
        """
        effective_limit = max_chars if max_chars is not None else (
            get_dynamic_max_chars(zone) if zone else 35000
        )
        if len(raw_content) <= effective_limit:
            return raw_content

        # 如果输出已经由具体工具做过落盘处理，仅做边界保护，避免二次落盘
        if "[系统提示: 完整原始输出" in raw_content or "[提示: 输出过长已精简" in raw_content:
            head_len = int(effective_limit * 0.7)
            tail_len = int(effective_limit * 0.3)
            omitted = len(raw_content) - head_len - tail_len
            return f"{raw_content[:head_len]}\n\n...[输出过长，已保护性省略中间 {omitted} 字符]...\n\n{raw_content[-tail_len:]}"

        return clamp_generic_output(raw_content, max_chars=effective_limit, tool_name=tool_name)

    def _build_step_banner(
        self,
        step: int,
        remaining_steps: Optional[int] = None,
        is_last_step: bool = False,
        is_near_end: bool = False,
        loop_state: Any = None,
        force_wrapup_active: bool = False
    ) -> str:
        """构建步数进度、倒计时与阶段引导横幅 (用于尾部单调注入)"""
        is_unbounded = (self.max_steps is None or self.max_steps <= 0)
        if force_wrapup_active or loop_state == LoopState.FORCE_WRAPUP:
            step_banner = self.loop_detector.get_wrapup_prompt_banner()
        elif is_unbounded:
            step_banner = f"[当前执行进度: 第 {step} 步 (自主无上限模式)]"
            if loop_state == LoopState.WARNING:
                step_banner += "\n" + self.loop_detector.get_warning_prompt_banner()
        else:
            step_banner = f"[当前执行进度: 第 {step}/{self.max_steps} 步 | 剩余 {remaining_steps} 步]"
            if loop_state == LoopState.WARNING:
                step_banner += "\n" + self.loop_detector.get_warning_prompt_banner()
            elif is_last_step:
                step_banner += " [重要提醒: 本轮已达最终步，工具调用已关闭。请基于上述已排查掌握的全部代码与事实，向用户输出详尽完整的最终分析答复或改动说明]"
            elif is_near_end:
                step_banner += " [提示: 步数即将耗尽，请尽快收拢排查，准备输出结论]"

        if not force_wrapup_active and loop_state != LoopState.FORCE_WRAPUP and not is_last_step and hasattr(self, "stage_manager") and self.stage_manager:
            step_banner += f"\n[{self.stage_manager.get_stage_banner()}]"

        return step_banner

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
            threshold_tokens = min(60000, max(16000, int(self.context_manager.budget.total_budget * 0.35)))

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

        try:
            from cli.ui import default_ui
            is_ui = default_ui.is_active
        except Exception:
            is_ui = False

        if not is_ui and verbose:
            zone_desc = f"{metrics['zone']} ({metrics['raw_utilization']*100:.1f}%)"
            gate_desc = " [已触发硬门禁截断]" if metrics.get("hard_gatekeeper_triggered") else ""
            print(f"\n{'='*20} 轮次 #{self.context_manager.turn_count} [水位: {zone_desc}{gate_desc}] | 引擎: {self.model} {'='*20}")
            print(f"用户目标: {user_prompt}\n")

        output_reserve = self.context_manager.budget.output_reserve
        turn_finished = False

        if not hasattr(self, "loop_detector") or self.loop_detector is None:
            self.loop_detector = LoopDetector()
        self.loop_detector.reset()
        if not hasattr(self, "stage_manager") or self.stage_manager is None:
            self.stage_manager = StageManager(enable_stage_masking=False)
        self.stage_manager.reset()

        if not hasattr(self, "max_steps"):
            self.max_steps = 0
        step = 0
        force_wrapup_active = False

        # 前缀缓存稳态保障：User 提问消息全周期保持不可变，从 Step 2 起的进度与阶段提示均单调追加至 Tool Result 末尾

        try:
            while True:
                step += 1
                is_unbounded = (self.max_steps is None or self.max_steps <= 0)

                # 若设置了固定步数上限，且当前步数超过上限，终止循环
                if not is_unbounded and step > self.max_steps:
                    break

                remaining_steps = None if is_unbounded else (self.max_steps - step)
                is_last_step = (not is_unbounded and step == self.max_steps)
                is_near_end = (not is_unbounded and remaining_steps is not None and remaining_steps <= 2 and self.max_steps > 3)

                # 1. 轮内步间动态 Token 预算核验与步间熔断（高优先级）
                current_context_tokens = self.context_manager.token_counter.count_messages(messages)
                max_context_allowed = self.context_manager.budget.total_budget - output_reserve - tools_tokens
                if step > 1 and current_context_tokens > max_context_allowed:
                    # 轮内触碰上限时，优先尝试动态梯队弹性扩容 (200k -> 250k -> 350k -> 500k)
                    total_needed = current_context_tokens + output_reserve + tools_tokens
                    if getattr(self.context_manager.budget, "auto_expand", False) and self.context_manager.budget.expand_if_needed(total_needed, threshold_ratio=0.85):
                        tier_info = self.context_manager.budget.get_tier_info()
                        max_context_allowed = self.context_manager.budget.total_budget - output_reserve - tools_tokens
                        logger.info(
                            f"轮内多步推理触发弹性扩容: Step {step} 动态扩展至 {tier_info['tier_name']} (上限 {self.context_manager.budget.total_budget} Tokens)。"
                        )
                        if verbose:
                            print(f"  [弹性扩容] 轮内多步推理消耗触达上限，动态扩展至 {tier_info['tier_name']} (上限 {self.context_manager.budget.total_budget:,} Tokens)")

                    # 若扩容后依然超限（例如已达 Tier 3 的 500k 极限），启动最后兜底：应急折叠早期超长工具观察结果
                    if current_context_tokens > max_context_allowed:
                        pruned_obs = self._prune_inturn_observations(messages)
                        if pruned_obs > 0:
                            current_context_tokens = self.context_manager.token_counter.count_messages(messages)
                            logger.info(f"轮内多步推理触发应急观察结果裁剪: Step {step} 折叠了 {pruned_obs} 条早期长工具输出。")
                            if verbose:
                                print(f"  [应急裁剪] 上下文濒临上限，已紧急折叠 {pruned_obs} 条早期长输出以避免熔断。")

                    # 若依然超过允许上限，执行安全熔断保护
                    if current_context_tokens > max_context_allowed:
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

                # 2. 状态判定与工具闭合控制 (Graceful Wrap-up):
                # 若到达最终步或死循环红牌强制收尾，关闭工具接口，迫使模型汇总事实输出最终解答
                loop_state = self.loop_detector.current_state
                call_tools = tools_schema if (tools_schema and not is_last_step and not force_wrapup_active and loop_state != LoopState.FORCE_WRAPUP) else None
                if call_tools:
                    call_tools = self.stage_manager.reorder_or_mask_schemas(call_tools)
                call_tool_choice = "auto" if call_tools else None

                if force_wrapup_active:
                    step_status = " [死循环熔断·强制收尾]"
                elif is_unbounded:
                    step_status = f" (第 {step} 步·自主排查)"
                elif is_last_step:
                    step_status = " (最终步收尾)"
                else:
                    step_status = f" (第 {step}/{self.max_steps} 步 | 剩余 {remaining_steps} 步)"

                if is_ui:
                    default_ui.render_step_status(step, self.max_steps, step_status)
                elif verbose:
                    print(f"[Step {step}] Agent 正在思考{step_status}...")

                # 3. 前缀缓存稳态保护 (Strict Append-Only)：
                # User 消息在 Step 1 注入初始 Banner 后终身只读，绝不回溯改写任何历史 User / Tool 消息。
                # 下一步的进度倒计时与阶段引导将在工具执行完毕后，单调追加至最新 Tool Result 尾部。

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
                    if is_ui:
                        default_ui.render_token_usage(prompt_toks, comp_toks, total_toks, self.model)
                    elif verbose:
                        print(f"  [API 实际用量] 输入: {prompt_toks} Tokens | 输出: {comp_toks} Tokens | 计费总计: {total_toks} Tokens")

                response_msg = response.choices[0].message
                assistant_dict = self._convert_response_to_dict(response_msg)

                if assistant_dict.get("tool_calls"):
                    messages.append(assistant_dict)
                    self.context_manager.add_assistant_message(assistant_dict)

                    if assistant_dict.get("content"):
                        if is_ui:
                            default_ui.render_thinking(assistant_dict["content"])
                        elif verbose:
                            print(f"  [Thought] {assistant_dict['content']}")

                    # 调度执行工具
                    tool_results = self.executor.execute_tool_calls(
                        response_msg.tool_calls,
                        verbose=verbose
                    )

                    # 单步工具输出保护与动态水位联动
                    current_zone = metrics.get("zone", "GREEN") if ("metrics" in locals() and isinstance(metrics, dict)) else "GREEN"
                    protected_results = []
                    for tr in tool_results:
                        call_id = tr.get("tool_call_id", "")
                        fname = "tool"
                        for tc in assistant_dict.get("tool_calls", []):
                            tc_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")
                            if tc_id == call_id:
                                fn = tc.get("function", {}) if isinstance(tc, dict) else getattr(tc, "function", None)
                                fname = fn.get("name", "tool") if isinstance(fn, dict) else getattr(fn, "name", "tool")
                                break

                        safe_content = self._protect_tool_result(
                            str(tr.get("content", "")),
                            zone=current_zone,
                            tool_name=fname
                        )
                        protected_results.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": safe_content
                        })

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
                        self.stage_manager.update_from_tool_call(
                            fname,
                            args_dict,
                            matched_res
                        )

                    # 记录并检测工具调用指纹与执行结果 (Loop & Stall Detection)
                    new_loop_state = self.loop_detector.record_step(
                        assistant_dict["tool_calls"],
                        protected_results
                    )
                    if new_loop_state == LoopState.FORCE_WRAPUP:
                        force_wrapup_active = True
                        if verbose:
                            print(f"\n  [死循环熔断] {self.loop_detector.diagnosis_reason} -> 下一步强制关闭工具收拢答复。")
                    elif new_loop_state == LoopState.WARNING:
                        if verbose:
                            print(f"  [停滞预警] {self.loop_detector.diagnosis_reason}")

                    # 轮内严格单调追加 (Strict Append-Only) 与 Prompt Cache 保障：
                    # 为下一步推理构建状态感知 Banner，并仅单调追加在最新一条 Tool 返回末尾，
                    # 绝不回溯篡改前序任何 User / Tool 消息，确保 Step 1 -> Step N 全程前缀逐字一致，100% 稳态命中大模型 KV Cache！
                    next_step = step + 1
                    next_remaining = None if is_unbounded else (self.max_steps - next_step)
                    next_is_last = (not is_unbounded and next_step == self.max_steps)
                    next_is_near = (not is_unbounded and next_remaining is not None and next_remaining <= 2 and self.max_steps > 3)

                    next_banner = self._build_step_banner(
                        step=next_step,
                        remaining_steps=next_remaining,
                        is_last_step=next_is_last,
                        is_near_end=next_is_near,
                        loop_state=new_loop_state,
                        force_wrapup_active=force_wrapup_active
                    )
                    if protected_results and next_banner:
                        protected_results[-1]["content"] += f"\n\n{next_banner}"

                    messages.extend(protected_results)
                    self.context_manager.add_tool_results(protected_results)
                    if new_loop_state == LoopState.FORCE_WRAPUP:
                        force_wrapup_active = True
                        if verbose:
                            print(f"\n  [死循环熔断] {self.loop_detector.diagnosis_reason} -> 下一步强制关闭工具收拢答复。")
                    elif new_loop_state == LoopState.WARNING:
                        if verbose:
                            print(f"  [停滞预警] {self.loop_detector.diagnosis_reason}")
                else:
                    if not is_ui and verbose:
                        if force_wrapup_active:
                            print(f"\n[安全收拢] Agent 响应死循环熔断，已向用户交付最终汇报。")
                        elif is_last_step:
                            print(f"\n[平滑收尾] Agent 在最终步 (第 {step} 步) 成功汇总事实并完成解答。")
                        else:
                            print(f"\n[任务达成] Agent 在第 {step} 步完成了本轮推理（无需继续调用工具，自然结束）。")

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
