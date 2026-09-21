# -*- coding: utf-8 -*-
"""
core/agent.py: 具备多步推理 (Thought -> Action -> Observation) 的 ReAct 智能体核心
"""
import os
import json
import atexit
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI

from tools import registry
from tools.executor import ToolExecutor, default_executor
from context import ContextManager, WorkingMemory
from mcp import McpManager, default_mcp_manager
from core.prompt import DEFAULT_SYSTEM_PROMPT

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

    def run(self, user_prompt: str, verbose: bool = True) -> str:
        """
        运行 ReAct 核心循环：
        User Turn -> Thought -> Action -> Observation -> ... -> Final Answer
        """
        # 1. 动态获取全量已注册工具清单并计算 Schema 占用的 Token 开销
        tools_schema = self.executor.registry.get_schemas()
        tools_json = json.dumps(tools_schema, ensure_ascii=False) if tools_schema else ""
        tools_tokens = self.context_manager.token_counter.count_text(tools_json)

        # 2. 开启新原子轮次
        self.context_manager.start_new_turn(user_prompt)

        # 3. 动态安全滑动窗口组装上下文（三段式水位控制 + 工具 Token 感知）
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

        for step in range(1, self.max_steps + 1):
            if verbose:
                print(f"[Step {step}/{self.max_steps}] Agent 正在思考...")

            # 显式传入 max_tokens 严格遵守账本 output_reserve 预算，杜绝输出超限
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools_schema if tools_schema else None,
                tool_choice="auto" if tools_schema else None,
                max_tokens=output_reserve
            )

            response_msg = response.choices[0].message

            if response_msg.tool_calls:
                messages.append(response_msg)
                self.context_manager.add_assistant_message(response_msg)

                if response_msg.content and verbose:
                    print(f"  [Thought] {response_msg.content}")

                # 统一安全执行调度（本地工具直调，MCP 工具管道代理，均走 ToolExecutor 沙箱）
                tool_results = self.executor.execute_tool_calls(
                    response_msg.tool_calls,
                    verbose=verbose
                )

                messages.extend(tool_results)

                # 观察阶段：更新工作区感知状态
                for tc in response_msg.tool_calls:
                    fname = tc.function.name
                    matched_res = next((tr["content"] for tr in tool_results if tr["tool_call_id"] == tc.id), "")
                    try:
                        args_dict = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except Exception:
                        args_dict = {}
                    self.context_manager.working_memory.update_from_tool(
                        fname,
                        args_dict,
                        matched_res
                    )

                self.context_manager.add_tool_results(tool_results)
            else:
                if verbose:
                    print(f"\n[任务达成] Agent 在第 {step} 步完成了本轮推理。")

                final_text = response_msg.content or "（无返回内容）"
                self.context_manager.add_assistant_message(response_msg)
                self.context_manager.finish_current_turn()
                return final_text

        fallback_msg = f"已达到最大执行步数限制 ({self.max_steps} 步)，强制结束任务以避免死循环。"
        if verbose:
            print(f"\n[警告] {fallback_msg}")
        self.context_manager.add_assistant_message(fallback_msg)
        self.context_manager.finish_current_turn()
        return fallback_msg
