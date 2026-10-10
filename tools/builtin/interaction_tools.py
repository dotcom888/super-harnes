# -*- coding: utf-8 -*-
"""
tools/builtin/interaction_tools.py: 用户交互与决策方案选择工具
支持 Agent 在需要人类决策时主动向前端弹出方案选择与自定义输入卡片。
"""
import time
import logging
from typing import Optional, List, Dict, Any, Callable
from tools.registry import register_tool

logger = logging.getLogger(__name__)

# 全局用户交互回调调度器 (由 AgentBridge 挂接)
_user_interaction_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None

def set_user_interaction_handler(handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]]):
    global _user_interaction_handler
    _user_interaction_handler = handler

def get_user_interaction_handler() -> Optional[Callable[[Dict[str, Any]], Dict[str, Any]]]:
    return _user_interaction_handler

@register_tool(
    name="ask_user",
    description="向用户主动发起方案确认或方案选择提问。当需要用户从多个选项中做出选择、确认关键变更方案，或提供补充输入时调用此工具。将在桌面端弹出会话决策卡片等待用户操作。",
    param_descriptions={
        "question": "向用户提出的核心问题或决策方案说明（例如：'请选择本次重构使用的底层方案：'）",
        "options": "供用户单选的方案列表（例如：['方案 A: 使用原生 WebSocket', '方案 B: 使用 REST 轮询']），可选",
        "header": "决策卡片的顶部标题（例如：'方案选择' 或 '决策确认'），可选，默认为'用户确认与决策'",
        "allow_custom": "是否允许用户输入自定义方案或补充说明，默认为 True"
    }
)
def ask_user(
    question: str,
    options: Optional[List[str]] = None,
    header: Optional[str] = "用户确认与决策",
    allow_custom: bool = True
) -> str:
    """
    向用户提出方案选择或确认卡片，等待用户在桌面端选择或输入后返回结果
    """
    handler = get_user_interaction_handler()
    if handler is None:
        first_opt = (options[0] if options else '默认采纳')
        return f"【系统提示】当前环境未启用图形交互界面。默认采纳第 1 个方案（{first_opt}），问题: {question}"

    payload = {
        "question": question,
        "options": options or [],
        "header": header or "用户确认与决策",
        "allow_custom": allow_custom
    }

    try:
        result = handler(payload)
        selected = result.get("selected_option", "").strip()
        custom = result.get("custom_input", "").strip()
        if not selected and not custom:
            return "【用户未选择或取消了操作】"
        res_parts = []
        if selected:
            res_parts.append(f"用户选择了方案: {selected}")
        if custom:
            res_parts.append(f"用户补充说明: {custom}")
        return "\n".join(res_parts)
    except Exception as e:
        logger.error(f"ask_user execution failed: {e}", exc_info=True)
        return f"用户交互卡片调用异常: {str(e)}"

@register_tool(
    name="request_user_input",
    description="向用户发起问题咨询、方案确认或选择。支持提供预设选项并接收用户自定义补充。",
    param_descriptions={
        "question": "向用户提出的问题或决策说明",
        "options": "可选的候选方案列表",
        "header": "卡片标题，可选",
        "allow_custom": "是否允许用户输入补充说明，默认为 True"
    }
)
def request_user_input(
    question: str,
    options: Optional[List[str]] = None,
    header: Optional[str] = "用户确认与决策",
    allow_custom: bool = True
) -> str:
    return ask_user(question=question, options=options, header=header, allow_custom=allow_custom)
