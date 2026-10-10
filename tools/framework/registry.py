# -*- coding: utf-8 -*-
import inspect
import typing
from typing import Callable, Any, Dict, List, Optional, Tuple
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


def _resolve_schema_type(annotation: Any) -> Tuple[str, Optional[Dict[str, Any]]]:
    """展开 typing.Optional / Union / List / Dict 等泛型注解，提取标准 JSON Schema 类型及子结构"""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return "string", None

    if annotation in TYPE_MAPPING:
        return TYPE_MAPPING[annotation], None

    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    # 展开 Optional[T] 或 Union[T, None]
    if origin is typing.Union:
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return _resolve_schema_type(non_none_args[0])
        elif non_none_args:
            return _resolve_schema_type(non_none_args[0])

    # 展开 List[T]
    if origin is list or origin is List:
        if args:
            item_type, item_extra = _resolve_schema_type(args[0])
            items_schema = {"type": item_type}
            if item_extra:
                items_schema.update(item_extra)
            return "array", {"items": items_schema}
        return "array", None

    # 展开 Dict[K, V]
    if origin is dict or origin is Dict:
        return "object", None

    return "string", None

class ToolRegistry:
    """工具注册中心：统一管理工具的注册、Schema 生成与函数分发"""
    def __init__(self):
        # 存储真实函数对象: {tool_name: func}
        self._tools: Dict[str, Callable] = {}
        # 存储大模型所需 JSON Schema: {tool_name: schema_dict}
        self._schemas: Dict[str, dict] = {}
        # 存储受保护的核心内置工具集合，禁止外部/MCP覆写
        self._immutable_tools: set = set()
        self._read_only_tools: set = set()

    def register(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        param_descriptions: Optional[Dict[str, str]] = None,
        immutable: bool = False,
        is_read_only: bool = False,
        parameters: Optional[Dict[str, str]] = None,
        read_only: Optional[bool] = None,
        **kwargs
    ):
        if param_descriptions is None and parameters is not None:
            param_descriptions = parameters
        if read_only is not None:
            is_read_only = read_only
        """
        装饰器：将一个普通的 Python 函数自动注册为 Agent 可调用的工具
        :param name: 工具名称（不传则默认取函数名）
        :param description: 工具描述（不传则默认取函数 docstring）
        :param param_descriptions: 参数描述字典，例如 {"expression": "要计算的表达式"}
        :param immutable: 是否将该工具标记为受保护内置工具（禁止覆写）
        """
        param_descriptions = param_descriptions or {}

        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            if tool_name in self._immutable_tools:
                raise PermissionError(f"安全拒绝：工具 '{tool_name}' 为受保护的内置核心工具，禁止覆盖！")

            tool_desc = description or (func.__doc__ or "无描述").strip()

            # 使用 inspect 模块自动提取函数的参数和类型注解
            sig = inspect.signature(func)
            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue

                param_type, extra_props = _resolve_schema_type(param.annotation)
                prop = {
                    "type": param_type,
                    "description": param_descriptions.get(param_name, f"参数 {param_name}")
                }
                if extra_props:
                    prop.update(extra_props)
                properties[param_name] = prop

                if param.default is inspect.Parameter.empty:
                    required.append(param_name)

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
            if immutable:
                self._immutable_tools.add(tool_name)
            if is_read_only:
                self._read_only_tools.add(tool_name)
            return func

        return decorator


    def mark_read_only(self, name: str, is_read_only: bool = True):
        """显式标记某个工具是否为只读工具"""
        if is_read_only:
            self._read_only_tools.add(name)
        else:
            self._read_only_tools.discard(name)

    def is_read_only(self, name: str) -> bool:
        """查询某个工具是否为纯只读安全工具"""
        return name in self._read_only_tools

    def lock_tool(self, name: str):
        """将某个工具名锁定为不可覆盖"""
        self._immutable_tools.add(name)

    def lock_all(self):
        """锁定当前注册表中的所有工具为不可覆盖"""
        self._immutable_tools.update(self._tools.keys())

    def register_mcp_proxy(self, name: str, proxy_func: Callable, schema: dict, is_read_only: bool = False):
        """专门供 MCP 桥接器注册外部工具的入口，实施严格的前缀与只读安全检查"""
        if not name.startswith("mcp__"):
            raise ValueError(f"MCP 扩展工具必须以 'mcp__' 为命名空间前缀，非法名称: '{name}'")
        if name in self._immutable_tools:
            raise PermissionError(f"安全拒绝：工具 '{name}' 与受保护的内置核心工具冲突，禁止覆盖！")
        self._tools[name] = proxy_func
        self._schemas[name] = schema
        if is_read_only:
            self._read_only_tools.add(name)

    def get_schemas(self) -> List[dict]:
        """获取所有已注册工具的 JSON Schema 清单，供传给大模型 tools=[...]"""
        return list(self._schemas.values())

    def get_tool_names(self) -> List[str]:
        """获取当前已注册的所有工具名称"""
        return list(self._tools.keys())

    def execute(self, name: str, args: Dict[str, Any]) -> str:
        """根据工具名称和参数字典安全执行真实函数"""
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
