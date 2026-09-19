# -*- coding: utf-8 -*-
import os
import sys
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI

from tools import registry
from tools.executor import ToolExecutor, default_executor
from session import Session, WorkingMemory

load_dotenv()

DEFAULT_SYSTEM_PROMPT = """你是一个具备高级多步推理和工具调用能力的代码工程 AI Agent。
你的任务是协助用户解决问题。你可以自主选择调用工具来收集信息或完成计算与代码修改。
原则：
1. 遇到复杂问题，可以分多步调用不同工具（如先搜索/读代码定位根因，再执行补丁修改，最后运行测试验证）；
2. 每次根据工具返回的结果继续推进思考，直到获得全部所需信息；
3. 具备多轮对话协同意识，充分利用上下文历史与工作区状态，避免重复读取已知文件；
4. 当信息充分且不需要再调工具时，给出清晰、精准、友好的最终结论。
"""

class ReActAgent:
    """
    具备多轮对话记忆、工作区状态感知与 ReAct 决策循环的智能体引擎
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_steps: int = 10,
        executor: Optional[ToolExecutor] = None,
        session: Optional[Session] = None
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.model = model or os.getenv("LLM_MODEL", "deepseek-chat")
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.executor = executor or default_executor
        self.session = session or Session("default")

        if not self.api_key or self.api_key == "your_api_key_here":
            raise ValueError("未检测到有效的 LLM_API_KEY，请检查 .env 文件！")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def reset_session(self):
        """重置当前会话记忆与工作区状态"""
        self.session.clear()

    def run(self, user_prompt: str, verbose: bool = True) -> str:
        """
        运行带记忆的多轮 ReAct 核心循环：
        User Turn -> Thought -> Action -> Observation -> ... -> Final Answer
        """
        # 1. 将用户输入加入当前多轮会话
        self.session.add_user_message(user_prompt)

        # 2. 动态组装上下文（注入 Working Memory 与剪枝后的历史）
        messages = self.session.build_messages(self.system_prompt)

        # 动态获取已注册工具清单
        tools_schema = self.executor.registry.get_schemas()

        if verbose:
            print(f"\n{'='*20} 开始处理任务 (轮次 #{self.session.turn_count}) {'='*20}")
            print(f"用户目标: {user_prompt}\n")

        for step in range(1, self.max_steps + 1):
            if verbose:
                print(f"[Step {step}/{self.max_steps}] Agent 正在思考...")

            # 1. 思考与决策阶段 (Thought)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools_schema if tools_schema else None,
                tool_choice="auto" if tools_schema else None
            )

            response_msg = response.choices[0].message

            # 2. 判断是否需要调用工具 (Action)
            if response_msg.tool_calls:
                # 记录模型意图与思考
                messages.append(response_msg)
                self.session.add_assistant_message(response_msg)

                if response_msg.content and verbose:
                    print(f"  [Thought] {response_msg.content}")

                # 3. 动作执行与观察阶段 (Action & Observation)
                tool_results = self.executor.execute_tool_calls(
                    response_msg.tool_calls,
                    verbose=verbose
                )

                # 将工具执行结果同步更新至工作区记忆 (Working Memory)
                for tc, tr in zip(response_msg.tool_calls, tool_results):
                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except Exception:
                        args = {}
                    self.session.working_memory.update_from_tool(
                        tc.function.name,
                        args,
                        tr.get("content", "")
                    )

                # 追加工具结果到当前推理上下文及持久化会话
                messages.extend(tool_results)
                self.session.add_tool_results(tool_results)
                # 继续进入下一个 step 循环
            else:
                # 4. 模型完成本轮推理，给出最终答案 (Final Answer)
                if verbose:
                    print(f"\n[任务达成] Agent 在第 {step} 步完成了本轮推理。")

                final_text = response_msg.content or "（无返回内容）"
                self.session.add_assistant_message(response_msg)

                # 轮次结束，触发历史超长观察的安全压缩，避免下一轮 Token 膨胀
                self.session.compact_history()
                return final_text

        # 超过最大步数熔断保护
        fallback_msg = f"已达到最大执行步数限制 ({self.max_steps} 步)，强制结束任务以避免死循环。"
        if verbose:
            print(f"\n[警告] {fallback_msg}")
        self.session.add_assistant_message(fallback_msg)
        return fallback_msg


def print_help():
    print("""
可用控制指令：
  /status, /memory  - 查看当前会话状态与工作区感知记忆（已读/已改文件、目标、测试状态）
  /new, /reset      - 清空会话历史与工作区记忆，开启全新排查任务
  /undo             - 回滚上一轮对话历史
  /history          - 查看会话历史简报
  /help             - 显示此帮助信息
  quit, exit        - 退出程序
""")

if __name__ == "__main__":
    print("正在启动 ReAct Agent 交互控制台 (多轮协同增强版)...")
    try:
        agent = ReActAgent(max_steps=10)
        print("Agent 就绪！已启用多轮对话记忆与工作区状态感知。输入 /help 查看协同指令。")

        while True:
            prompt = input("\n你: ").strip()
            if not prompt:
                continue

            cmd_lower = prompt.lower()
            if cmd_lower in ["quit", "exit"]:
                print("再见！")
                break
            elif cmd_lower in ["/new", "/clear", "/reset"]:
                agent.reset_session()
                print("【会话已重置】所有对话历史与工作区感知已清空，开启全新排查任务。")
                continue
            elif cmd_lower in ["/status", "/memory"]:
                wm = agent.session.working_memory
                print("\n" + "="*20 + " 当前工作区感知状态 " + "="*20)
                print(f"当前轮次: {agent.session.turn_count}")
                print(f"当前目标: {wm.current_goal or '（未指定）'}")
                print(f"已读文件: {list(wm.inspected_files.keys()) or '（无）'}")
                print(f"已改文件: {wm.modified_files or '（无）'}")
                print(f"最新测试: {wm.last_test_status or '（无）'}")
                print(f"消息总数: {len(agent.session.messages)} 条")
                print("="*60)
                continue
            elif cmd_lower == "/undo":
                if agent.session.rollback_last_turn():
                    print("【回滚成功】已撤销上一轮对话交互。")
                else:
                    print("【回滚失败】当前会话没有可回滚的轮次。")
                continue
            elif cmd_lower == "/history":
                print("\n" + "="*20 + " 会话历史摘要 " + "="*20)
                for idx, msg in enumerate(agent.session.messages, 1):
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    snippet = (content[:60] + "...") if content and len(content) > 60 else (content or "")
                    if role == "assistant" and msg.get("tool_calls"):
                        funcs = [tc['function']['name'] for tc in msg.get("tool_calls", [])]
                        snippet = f"调用工具: {', '.join(funcs)}"
                    print(f"[{idx}] {role}: {snippet}")
                print("="*54)
                continue
            elif cmd_lower == "/help":
                print_help()
                continue

            result = agent.run(prompt, verbose=True)
            print(f"\nAgent 最终答复:\n{result}")

    except Exception as e:
        print(f"初始化失败: {e}")
