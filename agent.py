# -*- coding: utf-8 -*-
import os
import sys
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI

from tools import registry
from tools.executor import ToolExecutor, default_executor

load_dotenv()

DEFAULT_SYSTEM_PROMPT = """你是一个具备高级多步推理和工具调用能力的 AI Agent。
你的任务是协助用户解决问题。你可以自主选择调用工具来收集信息或完成计算。
原则：
1. 遇到复杂问题，可以分多步调用不同工具（例如先查信息，再根据信息计算）；
2. 每次根据工具返回的结果继续推进思考，直到获得全部所需信息；
3. 当信息充分且不需要再调工具时，给出清晰、精准、友好的最终结论。
"""

class ReActAgent:
    """
    具备完整 ReAct (Reasoning + Acting) 决策循环的智能体引擎
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_steps: int = 10,
        executor: Optional[ToolExecutor] = None
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.model = model or os.getenv("LLM_MODEL", "deepseek-chat")
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.executor = executor or default_executor

        if not self.api_key or self.api_key == "your_api_key_here":
            raise ValueError("未检测到有效的 LLM_API_KEY，请检查 .env 文件！")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def run(self, user_prompt: str, verbose: bool = True) -> str:
        """
        运行 ReAct 核心循环：
        Thought -> Action -> Observation -> ... -> Final Answer
        """
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 动态获取已注册工具清单
        tools_schema = self.executor.registry.get_schemas()

        if verbose:
            print(f"\n{'='*20} 开始处理任务 {'='*20}")
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
                # 将模型的思考/意图加入上下文
                messages.append(response_msg)

                # 打印模型思考片段（若有文本输出）
                if response_msg.content and verbose:
                    print(f"  [Thought] {response_msg.content}")

                # 3. 动作执行与观察阶段 (Action & Observation)
                # 交给 ToolExecutor 统一调度
                tool_results = self.executor.execute_tool_calls(
                    response_msg.tool_calls,
                    verbose=verbose
                )

                # 将工具执行结果追加到对话消息列表中
                messages.extend(tool_results)
                # 继续进入下一个 step 循环，让大模型看到结果后决定下一步！
            else:
                # 4. 模型没有再发起工具调用，说明已得出最终答案 (Final Answer)
                if verbose:
                    print(f"\n[任务达成] Agent 在第 {step} 轮完成了推理。")
                return response_msg.content or "（无返回内容）"

        # 超过最大步数熔断保护
        fallback_msg = f"已达到最大执行步数限制 ({self.max_steps} 步)，强制结束任务以避免死循环。"
        if verbose:
            print(f"\n[警告] {fallback_msg}")
        return fallback_msg

if __name__ == "__main__":
    print("正在启动 ReAct Agent 交互控制台...")
    try:
        agent = ReActAgent(max_steps=10)
        print("Agent 就绪！当前支持多步推理与连续工具链调用。")
        print("测试示例：'请问当前系统时间是多少？然后帮我算一下，当前年份加上 50 是哪一年？'")

        while True:
            prompt = input("\n你: ").strip()
            if not prompt:
                continue
            if prompt.lower() in ["quit", "exit"]:
                print("再见！")
                break

            result = agent.run(prompt, verbose=True)
            print(f"\nAgent 最终答复:\n{result}")

    except Exception as e:
        print(f"初始化失败: {e}")
