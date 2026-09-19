# -*- coding: utf-8 -*-
import json
from typing import List, Optional
from openai import OpenAI
from context.window import TurnChunk

COMPACTION_SYSTEM_PROMPT = """你是一个专业的代码排查与修改上下文压缩器。
你的任务是将以下被淘汰的早期对话历史提炼为一份高密度的《历史排查与修改纪要》（300字以内）。
要求：
1. 提取已排查的代码文件与结论（确认无误的模块，防止后续重复排查）；
2. 提取已经进行的代码修改与涉及文件；
3. 提取用户给出的关键偏好、约束或目标转变；
4. 剔除寒暄、长篇日志与中间试探性输出，仅保留确定的工程事实。
如果提供了上一次的纪要，请将新信息与旧纪要合并更新。
"""

class ContextSummarizer:
    """
    历史排查摘要器：
    专职在水位超过红线 (>=75%) 时，将滑动窗口淘汰出的早期 TurnChunks 压缩为工程纪要。
    """
    def __init__(self, client: Optional[OpenAI] = None, model: str = "deepseek-chat"):
        self.client = client
        self.model = model
        self.current_summary: str = ""

    def _fallback_heuristic_summary(self, evicted_chunks: List[TurnChunk], previous_summary: str) -> str:
        """当无法调用大模型（无密钥/离线/API 波动）时的确定性规则兜底摘要"""
        touched_files = set()
        user_queries = []

        for chunk in evicted_chunks:
            for msg in chunk.messages:
                role = msg.get("role")
                if role == "user":
                    content = str(msg.get("content", "")).strip()
                    if content:
                        user_queries.append(content[:60])
                elif role == "tool":
                    # 从工具输出或参数提取相关文件
                    c = str(msg.get("content", ""))
                    if "文件" in c or "tools/" in c or ".py" in c:
                        for token in c.split():
                            if ".py" in token or "/" in token:
                                touched_files.add(token.strip("`'\"，。:;"))

        lines = []
        if previous_summary:
            lines.append(f"【前期汇总】: {previous_summary[:150]}...")
        if user_queries:
            recent_q = " -> ".join(user_queries[-4:])
            lines.append(f"- 早期排查轨迹: {recent_q}")
        if touched_files:
            files_str = ", ".join(list(touched_files)[:6])
            lines.append(f"- 涉及关键模块: {files_str}")

        return "\n".join(lines) if lines else "（已完成早期多轮代码排查与分析）"

    def summarize(
        self,
        evicted_chunks: List[TurnChunk],
        client: Optional[OpenAI] = None,
        model: Optional[str] = None
    ) -> str:
        """
        执行摘要压缩：优先调用轻量模型生成，若不可用则走兜底规则生成
        """
        if not evicted_chunks:
            return self.current_summary

        active_client = client or self.client
        active_model = model or self.model

        # 整理待摘要的对话文本
        formatted_history = []
        for chunk in evicted_chunks:
            formatted_history.append(f"--- 轮次 #{chunk.turn_id} ---")
            for msg in chunk.messages:
                role = msg.get("role")
                content = msg.get("content", "")
                if msg.get("tool_calls"):
                    tool_names = [tc['function']['name'] for tc in msg['tool_calls']]
                    formatted_history.append(f"assistant (调用工具): {', '.join(tool_names)}")
                elif role == "tool":
                    preview = (str(content)[:120] + "...") if len(str(content)) > 120 else str(content)
                    formatted_history.append(f"tool_result: {preview}")
                else:
                    preview = (str(content)[:120] + "...") if len(str(content)) > 120 else str(content)
                    formatted_history.append(f"{role}: {preview}")

        history_text = "\n".join(formatted_history)

        # 尝试通过大模型进行精准提炼
        if active_client:
            try:
                user_prompt = f"这是之前的排查纪要（若有）：\n{self.current_summary or '（无）'}\n\n这是本次新增淘汰的轮次：\n{history_text}\n\n请输出最新的《历史排查与修改纪要》："
                resp = active_client.chat.completions.create(
                    model=active_model,
                    messages=[
                        {"role": "system", "content": COMPACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=600,
                    temperature=0.3
                )
                generated = resp.choices[0].message.content
                if generated and generated.strip():
                    self.current_summary = generated.strip()
                    return self.current_summary
            except Exception:
                # API 异常时静默降级为兜底规则
                pass

        # 降级兜底方案
        self.current_summary = self._fallback_heuristic_summary(evicted_chunks, self.current_summary)
        return self.current_summary

    def clear(self):
        self.current_summary = ""
