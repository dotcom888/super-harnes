# -*- coding: utf-8 -*-
import inspect
from typing import Callable, Any, Dict, List, Optional
import json

# Python 类型到 OpenAI JSON Schema 类型的映射
TYPE_MAPPING = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}

class ToolRegistry:
    """工具注册中心：统一管理工具的注册、Schema 生成与函数分发"""
    def __init__(self):
        # 存储真实函数对象: {tool_name: func}
        self._tools: Dict[str, Callable] = {}
        # 存储大模型所需 JSON Schema: {tool_name: schema_dict}
        self._schemas: Dict[str, dict] = {}

    def register(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        param_descriptions: Optional[Dict[str, str]] = None
    ):
        """
        装饰器：将一个普通的 Python 函数自动注册为 Agent 可调用的工具
        :param name: 工具名称（不传则默认取函数名）
        :param description: 工具描述（不传则默认取函数 docstring）
        :param param_descriptions: 参数描述字典，例如 {"expression": "要计算的表达式"}
        """
        param_descriptions = param_descriptions or {}

        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            tool_desc = description or (func.__doc__ or "无描述").strip()

            # 使用 inspect 模块自动提取函数的参数和类型注解
            sig = inspect.signature(func)
            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                # 忽略 self/cls 或 *args, **kwargs
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue

                # 推导类型，未注解时默认为 string
                param_type = TYPE_MAPPING.get(param.annotation, "string")
                prop = {
                    "type": param_type,
                    "description": param_descriptions.get(param_name, f"参数 {param_name}")
                }
                properties[param_name] = prop

                # 如果没有默认值，则是必填项
                if param.default is inspect.Parameter.empty:
                    required.append(param_name)

            # 生成 OpenAI 兼容的 Function Calling Schema
            schema = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_desc,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            }

            self._tools[tool_name] = func
            self._schemas[tool_name] = schema
            return func

        return decorator

    def get_schemas(self) -> List[dict]:
        """获取所有已注册工具的 JSON Schema 清单，供传给大模型 tools=[...]"""
        return list(self._schemas.values())

    def get_tool_names(self) -> List[str]:
        """获取当前已注册的所有工具名称"""
        return list(self._tools.keys())

    def execute(self, name: str, args: Dict[str, Any]) -> str:
        """
        根据工具名称和参数字典安全执行真实函数。
        如果执行出错，将捕获异常并返回友好错误信息，避免主程序崩溃。
        """
        if name not in self._tools:
            return f"【工具执行失败】: 未知工具 '{name}'，当前可用工具有: {', '.join(self._tools.keys())}"

        func = self._tools[name]
        try:
            result = func(**args)
            return str(result)
        except Exception as e:
            return f"【工具执行出错】: {type(e).__name__}: {str(e)}"

# 创建全局默认单例实例
default_registry = ToolRegistry()
register_tool = default_registry.register
