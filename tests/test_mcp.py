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
from mcp.bridge import semantic_output_clamp, TMP_OUTPUT_DIR, _cleanup_old_spool_files

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

    def test_semantic_output_clamping_with_huge_errors(self):
        """验证海量递归堆栈报错（>100KB）下，不仅提取堆栈和错误，且绝不突破 max_chars 配额"""
        huge_err = (
            "Traceback (most recent call last):\n"
            + ("  File 'core.py', line 99, in recursive_calc\n" * 4000)
            + "RecursionError: maximum recursion depth exceeded while calling a Python object\n"
        )
        max_budget = 1200
        clamped = semantic_output_clamp(huge_err, max_chars=max_budget, server_id="test_srv", tool_name="test_fn")

        # 1. 严格预算约束：绝对不能超过给定的 max_chars
        self.assertLessEqual(len(clamped), max_budget)
        # 2. 关键错误上下文保留：头部 Traceback 与尾部核心 Exception 均被精准保留
        self.assertIn("Traceback (most recent call last):", clamped)
        self.assertIn("RecursionError:", clamped)
        # 3. 包含中间重复帧省略提示与本地落盘路径提示
        self.assertIn("堆栈过长已自动精简中间重复帧", clamped)
        self.assertIn("完整原始输出已存至:", clamped)

    def test_spool_file_rotation(self):
        """验证 .super-harnes/tmp 目录在文件过多时自动执行滚动淘汰，保证磁盘空间有界"""
        TMP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        # 创建 105 个模拟旧日志文件
        test_files = []
        for i in range(105):
            p = TMP_OUTPUT_DIR / f"mcp_test_rotation_{i:03d}.log"
            p.write_text(f"dummy log content {i}", encoding="utf-8")
            # 制造时间差
            mtime = time.time() - (105 - i) * 10
            os.utime(p, (mtime, mtime))
            test_files.append(p)

        try:
            # 触发清理，限定最多 100 个，淘汰至 70 个
            _cleanup_old_spool_files(TMP_OUTPUT_DIR, max_files=100, retain_files=70)
            remaining_test_files = list(TMP_OUTPUT_DIR.glob("mcp_test_rotation_*.log"))
            self.assertLessEqual(len(remaining_test_files), 70)
            # 验证保留的是时间最新的文件（索引较大的文件）
            self.assertTrue((TMP_OUTPUT_DIR / "mcp_test_rotation_104.log").exists())
            self.assertFalse((TMP_OUTPUT_DIR / "mcp_test_rotation_000.log").exists())
        finally:
            for p in TMP_OUTPUT_DIR.glob("mcp_test_rotation_*.log"):
                try:
                    p.unlink()
                except Exception:
                    pass

    def test_manager_handshake_failure_cleanup(self):
        """验证当 MCP 服务启动成功但握手失败时，子进程会被立即释放关闭，不成为会话期孤儿僵死进程"""
        test_reg = ToolRegistry()
        manager = McpManager(registry=test_reg)

        # 构造一个一启动就报错或不响应 JSON-RPC 的命令
        failing_code = "import sys, time; time.sleep(0.5); sys.exit(1)"
        cfg = McpServerConfig(
            server_id="broken_srv",
            command=sys.executable,
            args=["-c", failing_code],
            timeout_seconds=2
        )
        with self.assertRaises(Exception):
            manager._start_single_server("broken_srv", cfg)

        # 验证 broken_srv 没有残留在 manager.clients 中
        self.assertNotIn("broken_srv", manager.clients)

    def test_cascade_config_discovery_and_dual_base_resolution(self):
        """验证当工作区位于外部独立目录时，自动触发三级级联查找并回退至 Agent 内置保底配置"""
        import tempfile
        import shutil
        from tools.framework.workspace import default_workspace, set_workspace_root

        orig_root = default_workspace.root
        temp_dir = tempfile.mkdtemp(prefix="test_external_workspace_")
        temp_path = Path(temp_dir).resolve()

        try:
            # 切换工作区为完全空的临时目录（模拟用户在 C:\Users\Administrator 启动）
            set_workspace_root(temp_path)
            test_reg = ToolRegistry()
            manager = McpManager(registry=test_reg)

            # 1. 验证候选级联路径覆盖了临时工作区和 Agent 安装根目录
            candidates = manager.get_candidate_config_paths()
            self.assertTrue(any(temp_path in p.parents or p.parent == temp_path for p in candidates))

            # 2. 验证即便当前工作区无任何配置文件，仍能自动加载内置的 calculator 和 system_info
            loaded = manager.load_configs()
            self.assertIn("calculator", loaded)
            self.assertIn("system_info", loaded)

            # 3. 验证脚本路径双基准解析成功：calc_server.py 被解析为绝对路径且真实存在于磁盘
            calc_cfg = loaded["calculator"]
            self.assertTrue(len(calc_cfg.args) >= 1)
            resolved_script = Path(calc_cfg.args[0])
            self.assertTrue(resolved_script.is_absolute())
            self.assertTrue(resolved_script.exists())
            self.assertEqual(resolved_script.name, "calc_server.py")
        finally:
            set_workspace_root(orig_root)
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_project_level_mcp_config_override_and_merge(self):
        """验证项目级配置 (.super/mcp_servers.json) 与 Agent 内置配置的层级合并与优先覆盖"""
        import tempfile
        import shutil
        from tools.framework.workspace import default_workspace, set_workspace_root

        orig_root = default_workspace.root
        temp_dir = tempfile.mkdtemp(prefix="test_project_mcp_")
        temp_path = Path(temp_dir).resolve()

        try:
            set_workspace_root(temp_path)
            # 在项目工作区写入项目专属 .super/mcp_servers.json
            super_dir = temp_path / ".super"
            super_dir.mkdir(parents=True, exist_ok=True)
            proj_cfg_file = super_dir / "mcp_servers.json"
            proj_cfg_file.write_text(json.dumps({
                "mcpServers": {
                    "project_custom_srv": {
                        "command": "python",
                        "args": ["-c", "print('proj')"],
                        "timeout_seconds": 10
                    }
                }
            }), encoding="utf-8")

            test_reg = ToolRegistry()
            manager = McpManager(registry=test_reg)
            loaded = manager.load_configs()

            # 项目专属服务成功载入
            self.assertIn("project_custom_srv", loaded)
            # 全局/内置保底服务 (calculator) 同时保留合并
            self.assertIn("calculator", loaded)
        finally:
            set_workspace_root(orig_root)
            shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()
