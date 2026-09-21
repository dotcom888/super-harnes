# -*- coding: utf-8 -*-
"""
core/agent.py: 具备多步推理 (Thought -> Action -> Observation) 的 ReAct 智能体核心
"""
import os
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
        max_steps: int = 10,
        executor: Optional[ToolExecutor] = None,
        context_manager: Optional[ContextManager] = None,
        mcp_manager: Optional[McpManager] = None
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.model = model or os.getenv("LLM_MODEL", "deepseek-chat")
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.executor = executor or default_executor
        self.context_manager = context_manager or ContextManager("default")
        self.mcp_manager = mcp_manager or default_mcp_manager

        if not self.api_key or self.api_key == "your_api_key_here":
            raise ValueError("未检测到有效的 LLM_API_KEY，请检查 .env 文件！")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        # 自动挂载来自外部配置的 MCP 工具
        self.mcp_loaded = self.mcp_manager.start_and_bridge_all()
        # 退出时自动释放外部子进程
        atexit.register(self.mcp_manager.close_all)

    @property
    def session(self):
        """向后兼容属性"""
        return self.context_manager

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

    def _protect_tool_result(self, raw_content: str, max_chars: int = 2500) -> str:
        """单步工具输出保护：防止超大工具返回在轮内引发 Token 爆炸"""
        if len(raw_content) <= max_chars:
            return raw_content
        head_len = int(max_chars * 0.7)
        tail_len = int(max_chars * 0.3)
        omitted = len(raw_content) - head_len - tail_len
        return f"{raw_content[:head_len]}\n\n...[输出过长，已保护性省略中间 {omitted} 字符]...\n\n{raw_content[-tail_len:]}"

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
                if verbose:
                    print(f"[Step {step}/{self.max_steps}] Agent 正在思考...")

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools_schema if tools_schema else None,
                    tool_choice="auto" if tools_schema else None,
                    max_tokens=output_reserve
                )

                response_msg = response.choices[0].message
                # 关键修复：统一转换为纯字典
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

                    # 关键修复：单步工具输出保护，防止轮内爆炸
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
                        self.context_manager.working_memory.update_from_tool(
                            fname,
                            args_dict,
                            matched_res
                        )

                    # 关键修复：轮内即时同步工作记忆注记，让随后的 step 感知最新状态
                    latest_wm = self.context_manager.working_memory.format_prompt_context()
                    for m in messages:
                        if m.get("role") == "user" and "【系统注记 - 工作区感知状态" in str(m.get("content", "")):
                            parts = str(m.get("content", "")).split("[用户当前输入]:", 1)
                            user_suffix = parts[1] if len(parts) > 1 else ""
                            m["content"] = f"{latest_wm}\n\n[用户当前输入]:{user_suffix}"
                            break

                    self.context_manager.add_tool_results(protected_results)
                else:
                    if verbose:
                        print(f"\n[任务达成] Agent 在第 {step} 步完成了本轮推理。")

                    final_text = assistant_dict.get("content") or "（无返回内容）"
                    self.context_manager.add_assistant_message(assistant_dict)
                    self.context_manager.finish_current_turn()
                    turn_finished = True
                    return final_text

            fallback_msg = f"已达到最大执行步数限制 ({self.max_steps} 步)，强制结束任务以避免死循环。"
            if verbose:
                print(f"\n[警告] {fallback_msg}")
            self.context_manager.add_assistant_message(fallback_msg)
            self.context_manager.finish_current_turn()
            turn_finished = True
            return fallback_msg

        finally:
            # 事务性保障：若异常中断导致未完成，强制安全关闭轮次，杜绝悬挂半截脏轮次
            if not turn_finished and self.context_manager.current_turn:
                logger.warning("轮次未正常完成即退出，执行防御性轮次收尾。")
                self.context_manager.finish_current_turn()
