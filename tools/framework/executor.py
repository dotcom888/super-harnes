# -*- coding: utf-8 -*-
import json
from typing import List, Dict, Any
from tools.registry import ToolRegistry, default_registry

class ToolExecutor:
    """
    工具执行器：负责安全调度、批量执行大模型发起的 tool_calls，
    并将执行结果格式化为标准 OpenAI 消息格式。
    """
    def __init__(self, registry: ToolRegistry = default_registry):
        self.registry = registry

    def execute_tool_calls(self, tool_calls: List[Any], verbose: bool = True) -> List[Dict[str, Any]]:
        """
        批量执行由模型触发的 tool_calls
        :param tool_calls: 大模型响应中的 response_msg.tool_calls
        :param verbose: 是否在控制台打印执行日志
        :return: 包装好的 [{'role': 'tool', 'tool_call_id': ..., 'content': ...}, ...]
        """
        tool_messages = []

        for tc in tool_calls:
            func_name = tc.function.name
            raw_args = tc.function.arguments

            # 1. 尝试解析参数 JSON
            try:
                args = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError as err:
                error_msg = f"参数 JSON 格式解析失败: {str(err)}。传入参数为: {raw_args}"
                if verbose:
                    print(f"  [Executor 警告] 工具 '{func_name}' {error_msg}")
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": error_msg
                })
                continue

            if verbose:
                print(f"  [Action] 正在执行工具 -> 【{func_name}】")
                print(f"           输入参数: {json.dumps(args, ensure_ascii=False)}")

            # 2. 调用 registry 执行真实函数（内置异常捕获机制）
            result = self.registry.execute(func_name, args)

            if verbose:
                # 截断过长日志以保证控制台整洁
                preview = result[:200] + "..." if len(result) > 200 else result
                print(f"  [Observation] 工具返回结果 -> {preview}")

            # 3. 构造符合规范的 tool 消息
            tool_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result)
            })

        return tool_messages

default_executor = ToolExecutor()
