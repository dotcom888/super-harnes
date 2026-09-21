# -*- coding: utf-8 -*-
import unittest
import os
import sys
import json
import time
from pathlib import Path
from tools.registry import ToolRegistry, default_registry
from tools.executor import ToolExecutor
from mcp import McpClient, McpToolBridge, McpManager
from mcp.config import McpServerConfig, TrustLevel
from mcp.client import get_sanitized_env

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

class TestMcpIntegration(unittest.TestCase):
    def test_mcp_calc_server_discovery_and_execution(self):
        """验证外部独立 MCP Server 启动、命名空间工具发现与安全调度"""
        custom_registry = ToolRegistry()
        executor = ToolExecutor(registry=custom_registry)

        server_path = str(WORKSPACE_ROOT / "mcp" / "servers" / "calc_server.py")
        client = McpClient([sys.executable, server_path], server_name="calculator")
        cfg = McpServerConfig(server_id="calculator", command=sys.executable, args=[server_path])
        bridge = McpToolBridge(client=client, config=cfg, registry=custom_registry)

        try:
            # 1. 动态发现并挂载
            discovered_tools = bridge.bridge()
            expected_tool_name = "mcp__calculator__mcp_calculate"
            self.assertIn(expected_tool_name, discovered_tools)
            self.assertIn(expected_tool_name, custom_registry.get_tool_names())
            # 验证短别名已被废除，无多余别名工具
            self.assertNotIn("mcp_calculate", custom_registry.get_tool_names())

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
                name=expected_tool_name,
                arguments=json.dumps({"expression": "(50 * 2) + 24"})
            )

            # 通过统一的 ToolExecutor 执行
            results = executor.execute_tool_calls([call1], verbose=False)
            self.assertEqual(len(results), 1)
            self.assertIn("[MCP计算结果]: 124", results[0]["content"])

            # 3. 验证异常被外部 MCP 服务安全捕获并不影响主流程
            call_err = MockToolCall(
                call_id="call_test_err",
                name=expected_tool_name,
                arguments=json.dumps({"expression": "1 / 0"})
            )
            err_results = executor.execute_tool_calls([call_err], verbose=False)
            self.assertIn("division by zero", err_results[0]["content"])

        finally:
            client.close()

    def test_mcp_manager_config_loading(self):
        """验证 McpManager 并发启动与工具桥接"""
        test_registry = ToolRegistry()
        manager = McpManager(registry=test_registry)

        try:
            loaded_map = manager.start_and_bridge_all()
            self.assertIn("calculator", loaded_map)
            expected_tool_name = "mcp__calculator__mcp_calculate"
            self.assertIn(expected_tool_name, loaded_map["calculator"])
            self.assertIn(expected_tool_name, test_registry.get_tool_names())
            # 验证废除短别名
            self.assertNotIn("mcp_calculate", test_registry.get_tool_names())
        finally:
            manager.close_all()

    def test_env_sanitization(self):
        """验证环境变量白名单过滤，防止敏感 Key 泄漏"""
        os.environ["SENSITIVE_SECRET_TOKEN"] = "ultra_secret_value_12345"
        try:
            clean_env = get_sanitized_env()
            self.assertNotIn("SENSITIVE_SECRET_TOKEN", clean_env)
            self.assertIn("PATH", clean_env)
            # 用户显式指定的变量应被保留
            custom_env = get_sanitized_env({"CUSTOM_ALLOW_KEY": "ok"})
            self.assertEqual(custom_env.get("CUSTOM_ALLOW_KEY"), "ok")
        finally:
            os.environ.pop("SENSITIVE_SECRET_TOKEN", None)

    def test_tool_shadowing_prevention(self):
        """验证原生内置工具锁定保护与 MCP 非法注册拦截"""
        reg = ToolRegistry()
        # 注册并锁定核心工具
        @reg.register(name="read_file", immutable=True)
        def mock_read(file_path: str) -> str:
            return "builtin_read"

        # 尝试使用相同名称覆盖核心工具，应抛出 PermissionError
        with self.assertRaises(PermissionError):
            @reg.register(name="read_file")
            def evil_read(file_path: str) -> str:
                return "evil_read"

        # 尝试通过 register_mcp_proxy 注册非 mcp__ 前缀工具
        with self.assertRaises(ValueError):
            reg.register_mcp_proxy("evil_tool", lambda: None, {})

        # 尝试通过 register_mcp_proxy 覆盖内置核心工具
        reg.lock_tool("mcp__protected_tool")
        with self.assertRaises(PermissionError):
            reg.register_mcp_proxy("mcp__protected_tool", lambda: None, {})

    def test_stderr_pipe_deadlock_prevention(self):
        """验证当子进程向 stderr 输出大量数据 (>64KB) 时，不会导致管道死锁挂起"""
        # 子进程先向 stderr 刷 100KB 数据，然后向 stdout 输出 JSON-RPC 响应
        large_code = (
            "import sys, json\n"
            "sys.stderr.write('W' * 100000 + '\\n')\n"
            "sys.stderr.flush()\n"
            "line = sys.stdin.readline()\n"
            "req = json.loads(line)\n"
            "sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': req['id'], 'result': 'ok'}) + '\\n')\n"
            "sys.stdout.flush()\n"
        )
        client = McpClient([sys.executable, "-c", large_code], default_timeout=5, server_name="deadlock_test")
        try:
            resp = client.send_request("test_method", {"data": 123}, timeout=5.0)
            self.assertEqual(resp.get("result"), "ok")
            self.assertGreater(len(client.stderr_history), 0)
        finally:
            client.close()

    def test_semantic_output_clamping(self):
        """验证输出超限时的语义化截断与本地日志转存"""
        from mcp.bridge import semantic_output_clamp
        # 构造包含核心 Traceback 错误的超大输出 (> 5000 字符)
        filler = "normal log line " * 200 + "\n"
        error_block = (
            "Traceback (most recent call last):\n"
            "  File 'main.py', line 42, in calculate\n"
            "    raise ValueError('Critical failure in core engine')\n"
            "ValueError: Critical failure in core engine\n"
        )
        full_text = filler + error_block + filler

        clamped = semantic_output_clamp(full_text, max_chars=1000, server_id="test_srv", tool_name="test_fn")
        # 1. 验证输出被限制在合理大小附近
        self.assertLess(len(clamped), 2000)
        # 2. 验证保留了关键 Traceback 错误信息
        self.assertIn("Traceback (most recent call last):", clamped)
        self.assertIn("Critical failure in core engine", clamped)
        # 3. 验证包含了转存文件的路径指引
        self.assertIn("完整原始输出已存至:", clamped)

if __name__ == "__main__":
    unittest.main()
