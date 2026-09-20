# -*- coding: utf-8 -*-
import json
from typing import List, Dict, Any, Callable
from mcp.client import McpClient
from mcp.config import McpServerConfig, TrustLevel
from tools.registry import ToolRegistry
from tools.policies import default_policy

class McpToolBridge:
    """
    加固型 MCP 工具桥接器：
    1. 命名空间隔离：强制统一前缀格式 `mcp__{server_id}__{tool_name}`，消除命名碰撞；
    2. 输出限额截断 (Output Clamping)：保护上下文不被超大返回数据击穿；
    3. 信任等级控制 (Trust Level Policy)：支持免审批、人工确认与黑名单拦截；
    4. 异常安全降级：捕获超时与崩溃，绝不破坏 ReAct 循环。
    """
    def __init__(self, client: McpClient, config: McpServerConfig, registry: ToolRegistry):
        self.client = client
        self.config = config
        self.registry = registry
        self.bridged_tool_names: List[str] = []

    def bridge(self) -> List[str]:
        # 1. 握手能力协商
        self.client.send_request("initialize", timeout=self.config.timeout_seconds)

        # 2. 动态拉取工具清单
        resp = self.client.send_request("tools/list", timeout=self.config.timeout_seconds)
        tools = resp.get("result", {}).get("tools", [])

        for tool_meta in tools:
            raw_name = tool_meta["name"]
            raw_desc = tool_meta.get("description", "外部 MCP 工具")
            input_schema = tool_meta.get("inputSchema", {})

            # 3. 命名空间前缀化：mcp__{server_id}__{tool_name}
            namespaced_name = f"mcp__{self.config.server_id}__{raw_name}"
            enhanced_desc = f"[{self.config.server_id.upper()} MCP] {raw_desc}"

            # 构造 OpenAI Function Calling Schema
            internal_schema = {
                "type": "function",
                "function": {
                    "name": namespaced_name,
                    "description": enhanced_desc,
                    "parameters": input_schema
                }
            }

            # 4. 生成带超时、输出限额与信任等级防护的闭包代理
            def _create_proxy(target_raw_name: str, full_name: str) -> Callable:
                def proxy_func(**kwargs) -> str:
                    # 信任等级 1: 黑名单拦截
                    if self.config.trust_level == TrustLevel.BLOCKED:
                        return f"【安全拦截拒绝】：MCP 服务 '{self.config.server_id}' 处于禁用黑名单，禁止调用！"

                    # 信任等级 2: 人工审批拦截 (Human-in-the-Loop)
                    if self.config.trust_level == TrustLevel.REQUIRE_APPROVAL:
                        reason = f"外部 MCP 工具 '{full_name}' 属于非完全受信来源，调用参数: {json.dumps(kwargs, ensure_ascii=False)}"
                        is_approved = default_policy.request_approval(full_name, reason)
                        if not is_approved:
                            return f"【用户拒绝】：用户在终端取消或拒绝了外部 MCP 工具 '{full_name}' 的执行申请。"

                    # 执行远程调用（施加超时保护）
                    try:
                        call_resp = self.client.send_request(
                            "tools/call",
                            {"name": target_raw_name, "arguments": kwargs},
                            timeout=self.config.timeout_seconds
                        )
                    except TimeoutError as te:
                        return f"【MCP 调用超时】：外部服务 '{self.config.server_id}' 响应超过 {self.config.timeout_seconds} 秒上限已终止。"
                    except Exception as err:
                        return f"【MCP 通信异常】：{type(err).__name__}: {str(err)}"

                    result_data = call_resp.get("result", {})
                    if result_data.get("isError"):
                        return f"【MCP 执行报错】: {json.dumps(result_data.get('content', []), ensure_ascii=False)}"

                    contents = result_data.get("content", [])
                    text_parts = [c.get("text", "") for c in contents if c.get("type") == "text"]
                    raw_result = "\n".join(text_parts) if text_parts else str(result_data)

                    # 5. 输出限额截断保护 (Output Clamping)
                    max_chars = self.config.max_output_chars
                    if len(raw_result) > max_chars:
                        head = raw_result[: int(max_chars * 0.6)]
                        tail = raw_result[- int(max_chars * 0.3):]
                        omitted = len(raw_result) - len(head) - len(tail)
                        raw_result = (
                            f"{head}\n\n"
                            f"... [外部 MCP 输出过大，已自动截断省略 {omitted} 字符，请使用更精准的参数查询] ...\n\n"
                            f"{tail}"
                        )

                    return raw_result

                proxy_func.__name__ = namespaced_name
                proxy_func.__doc__ = enhanced_desc
                return proxy_func

            # 注册到内部注册表
            self.registry._schemas[namespaced_name] = internal_schema
            self.registry._tools[namespaced_name] = _create_proxy(raw_name, namespaced_name)
            self.bridged_tool_names.append(namespaced_name)

        return self.bridged_tool_names
