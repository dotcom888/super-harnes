# -*- coding: utf-8 -*-
import json
from typing import List, Dict, Any, Callable
from mcp.client import McpClient
from tools.registry import ToolRegistry

class McpToolBridge:
    """
    MCP 核心桥接器：
    负责将外部 MCP Server 暴露的工具能力无缝接入到内部统一的 ToolRegistry 中。
    核心原则：
    1. 动态发现：启动时向 Server 发起 tools/list，不硬编码任何工具定义；
    2. 统一抽象：桥接为与本地工具一模一样的 Function Calling Schema；
    3. 代理执行：生成远程代理闭包，自动通过 stdio 转发 tools/call；
    4. 接入安全体系：依然接受 ToolExecutor 的参数反序列化、异常拦截与输出保护。
    """
    def __init__(self, client: McpClient, registry: ToolRegistry):
        self.client = client
        self.registry = registry
        self.bridged_tool_names: List[str] = []

    def bridge(self) -> List[str]:
        """执行握手、动态发现并挂载到 ToolRegistry"""
        # 1. 协议握手
        self.client.send_request("initialize")

        # 2. 动态获取外部工具清单
        resp = self.client.send_request("tools/list")
        tools = resp.get("result", {}).get("tools", [])

        for tool_meta in tools:
            name = tool_meta["name"]
            desc = tool_meta.get("description", "外部 MCP 工具")
            input_schema = tool_meta.get("inputSchema", {})

            # 3. 构造 OpenAI Function Calling Schema
            internal_schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": input_schema
                }
            }

            # 4. 生成调用闭包代理函数 (Proxy Callable)
            def _create_proxy(target_name: str) -> Callable:
                def proxy_func(**kwargs) -> str:
                    call_resp = self.client.send_request("tools/call", {
                        "name": target_name,
                        "arguments": kwargs
                    })

                    result_data = call_resp.get("result", {})
                    if result_data.get("isError"):
                        return f"【MCP 工具执行错误】: {json.dumps(result_data.get('content', []), ensure_ascii=False)}"

                    contents = result_data.get("content", [])
                    text_parts = [c.get("text", "") for c in contents if c.get("type") == "text"]
                    return "\n".join(text_parts) if text_parts else str(result_data)

                proxy_func.__name__ = target_name
                proxy_func.__doc__ = desc
                return proxy_func

            # 5. 挂入内部统一注册表
            self.registry._schemas[name] = internal_schema
            self.registry._tools[name] = _create_proxy(name)
            self.bridged_tool_names.append(name)

        return self.bridged_tool_names
