# -*- coding: utf-8 -*-
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
from mcp.client import McpClient
from mcp.bridge import McpToolBridge
from tools.registry import ToolRegistry, default_registry

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

class McpManager:
    """
    统一 MCP 生命周期管理器：
    1. 解析 mcp_servers.json 配置文件；
    2. 启动并托管外部子进程 MCP Server；
    3. 通过 McpToolBridge 自动把所有服务发现的工具注册到 ToolRegistry 中；
    4. 程序退出时统一安全终止子进程。
    """
    def __init__(self, config_path: Optional[str] = None, registry: ToolRegistry = default_registry):
        self.config_path = Path(config_path) if config_path else (WORKSPACE_ROOT / "mcp_servers.json")
        self.registry = registry
        self.clients: Dict[str, McpClient] = {}
        self.bridges: Dict[str, McpToolBridge] = {}

    def start_and_bridge_all(self) -> Dict[str, List[str]]:
        """从配置文件启动所有配置的 MCP Server 并完成工具桥接"""
        if not self.config_path.exists():
            return {}

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception as e:
            sys.stderr.write(f"读取 MCP 配置文件失败: {e}\n")
            return {}

        servers_cfg = config_data.get("mcpServers", {})
        loaded_tools_map = {}

        for server_id, spec in servers_cfg.items():
            cmd = spec.get("command", "")
            args = spec.get("args", [])
            env = spec.get("env", None)

            # 智能替换：如果 command 为 python，优先使用当前虚拟环境的 python.exe
            if cmd == "python" or cmd == "python3":
                resolved_cmd = sys.executable
            else:
                resolved_cmd = cmd

            full_command = [resolved_cmd] + args

            try:
                client = McpClient(command=full_command, env=env)
                bridge = McpToolBridge(client=client, registry=self.registry)
                discovered = bridge.bridge()

                self.clients[server_id] = client
                self.bridges[server_id] = bridge
                loaded_tools_map[server_id] = discovered
            except Exception as e:
                sys.stderr.write(f"启动 MCP Server '{server_id}' 失败: {e}\n")

        return loaded_tools_map

    def close_all(self):
        """关闭所有正在运行的 MCP 服务进程"""
        for server_id, client in list(self.clients.items()):
            try:
                client.close()
            except Exception:
                pass
        self.clients.clear()
        self.bridges.clear()

default_mcp_manager = McpManager()
