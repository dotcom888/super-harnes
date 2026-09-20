# -*- coding: utf-8 -*-
import unittest
import sys
import json
from pathlib import Path
from tools.registry import ToolRegistry
from tools.executor import ToolExecutor
from mcp import McpClient, McpToolBridge, McpManager

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

class TestMcpIntegration(unittest.TestCase):
    def test_mcp_calc_server_discovery_and_execution(self):
        """验证外部独立 MCP Server 启动、动态工具发现、注册到 ToolRegistry 及 ToolExecutor 安全调度"""
        custom_registry = ToolRegistry()
        executor = ToolExecutor(registry=custom_registry)

        server_path = str(WORKSPACE_ROOT / "mcp" / "servers" / "calc_server.py")
        client = McpClient([sys.executable, server_path])
        bridge = McpToolBridge(client=client, registry=custom_registry)

        try:
            # 1. 动态发现并挂载
            discovered_tools = bridge.bridge()
            self.assertIn("mcp_calculate", discovered_tools)
            self.assertIn("mcp_calculate", custom_registry.get_tool_names())

            # 2. 模拟大模型发起正常工具调用
            class MockFunction:
                def __init__(self, name, arguments):
                    self.name = name
                    self.arguments = arguments

            class MockToolCall:
                def __init__(self, call_id, name, arguments):
                    self.id = call_id
                    self.function = MockFunction(name, arguments)

            call1 = MockToolCall(
                call_id="call_test_1",
                name="mcp_calculate",
                arguments=json.dumps({"expression": "(50 * 2) + 24"})
            )

            # 通过统一的 ToolExecutor 执行
            results = executor.execute_tool_calls([call1], verbose=False)
            self.assertEqual(len(results), 1)
            self.assertIn("[MCP计算结果]: 124", results[0]["content"])

            # 3. 验证异常被外部 MCP 服务安全捕获并不影响主流程
            call_err = MockToolCall(
                call_id="call_test_err",
                name="mcp_calculate",
                arguments=json.dumps({"expression": "1 / 0"})
            )
            err_results = executor.execute_tool_calls([call_err], verbose=False)
            self.assertIn("division by zero", err_results[0]["content"])

        finally:
            client.close()

    def test_mcp_manager_config_loading(self):
        """验证 McpManager 从 mcp_servers.json 配置文件批量启动与桥接"""
        test_registry = ToolRegistry()
        manager = McpManager(registry=test_registry)

        try:
            loaded_map = manager.start_and_bridge_all()
            self.assertIn("calculator", loaded_map)
            self.assertIn("mcp_calculate", loaded_map["calculator"])
            self.assertIn("mcp_calculate", test_registry.get_tool_names())
        finally:
            manager.close_all()

if __name__ == "__main__":
    unittest.main()
