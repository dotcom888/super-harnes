# -*- coding: utf-8 -*-
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
from mcp.client import McpClient
from mcp.config import McpServerConfig, TrustLevel
from mcp.bridge import McpToolBridge
from tools.registry import ToolRegistry, default_registry

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

class McpManager:
    """
    加固型 MCP 生命周期与服务调度管理器：
    1. 配置模式校验 (Config Validation)；
    2. 单点故障隔离 (Fault Isolation)：单个 Server 配置错误或启动失败绝不影响 Agent 全局；
    3. 服务状态追踪与安全退出清理。
    """
    def __init__(self, config_path: Optional[str] = None, registry: ToolRegistry = default_registry):
        self.config_path = Path(config_path) if config_path else (WORKSPACE_ROOT / "mcp_servers.json")
        self.registry = registry
        self.clients: Dict[str, McpClient] = {}
        self.configs: Dict[str, McpServerConfig] = {}
        self.bridges: Dict[str, McpToolBridge] = {}
        self.server_status: Dict[str, str] = {}  # {server_id: "RUNNING" | "FAILED" | "STOPPED"}

    def start_and_bridge_all(self) -> Dict[str, List[str]]:
        if not self.config_path.exists():
            return {}

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except Exception as e:
            print(f"[MCP 警告] 解析配置文件 '{self.config_path}' 失败: {e}，跳过外部 MCP 加载。")
            return {}

        servers_dict = raw_data.get("mcpServers", {})
        loaded_tools_map = {}

        for server_id, raw_spec in servers_dict.items():
            # 1. 严格配置校验（单点故障隔离：坏配置不拖垮整体）
            try:
                config = McpServerConfig.from_dict(server_id, raw_spec)
                self.configs[server_id] = config
            except Exception as val_err:
                print(f"[MCP 警告] 忽略损坏的服务配置 '{server_id}': {val_err}")
                self.server_status[server_id] = f"CONFIG_ERROR: {val_err}"
                continue

            # 2. 解析命令与路径
            cmd = config.command
            if cmd in ("python", "python3"):
                resolved_cmd = sys.executable
            else:
                resolved_cmd = cmd

            full_command = [resolved_cmd] + config.args

            # 3. 启动子进程并桥接（实施 Fault Isolation）
            try:
                client = McpClient(
                    command=full_command,
                    env=config.env,
                    cwd=config.cwd,
                    default_timeout=config.timeout_seconds
                )
                bridge = McpToolBridge(
                    client=client,
                    config=config,
                    registry=self.registry
                )
                discovered = bridge.bridge()

                self.clients[server_id] = client
                self.bridges[server_id] = bridge
                self.server_status[server_id] = "RUNNING"
                loaded_tools_map[server_id] = discovered
            except Exception as start_err:
                print(f"[MCP 警告] 服务 '{server_id}' 启动或握手失败 ({type(start_err).__name__}: {start_err})，已安全跳过。")
                self.server_status[server_id] = f"START_FAILED: {start_err}"

        return loaded_tools_map

    def close_all(self):
        """统一安全回收所有外部服务子进程"""
        for server_id, client in list(self.clients.items()):
            try:
                client.close()
                self.server_status[server_id] = "STOPPED"
            except Exception:
                pass
        self.clients.clear()
        self.bridges.clear()

default_mcp_manager = McpManager()
