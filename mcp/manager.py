# -*- coding: utf-8 -*-
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from mcp.client import McpClient
from mcp.config import McpServerConfig, TrustLevel
from mcp.bridge import McpToolBridge
from tools.framework.registry import ToolRegistry, default_registry

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

class McpManager:
    """
    加固型 MCP 管理器：
    1. 统一管理多个独立外部进程服务的生命周期；
    2. 集中化安全参数（TrustLevel、超时、限额）校验；
    3. 服务状态追踪与安全退出清理。
    """
    def __init__(self, config_path: Optional[str] = None, registry: ToolRegistry = default_registry):
        if config_path:
            self.config_path = Path(config_path)
        else:
            preferred = WORKSPACE_ROOT / "config" / "mcp_servers.json"
            self.config_path = preferred if preferred.exists() else (WORKSPACE_ROOT / "mcp_servers.json")

        self.registry = registry
        self.clients: Dict[str, McpClient] = {}
        self.configs: Dict[str, McpServerConfig] = {}

    def load_configs(self) -> Dict[str, McpServerConfig]:
        if not self.config_path.exists():
            return {}

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        servers_dict = data.get("mcpServers", {})
        loaded = {}
        for server_id, raw_cfg in servers_dict.items():
            cfg = McpServerConfig(
                server_id=server_id,
                command=raw_cfg.get("command", ""),
                args=raw_cfg.get("args", []),
                env=raw_cfg.get("env"),
                cwd=raw_cfg.get("cwd") or str(WORKSPACE_ROOT),
                trust_level=raw_cfg.get("trust_level", TrustLevel.TRUSTED),
                timeout_seconds=raw_cfg.get("timeout_seconds", 20),
                max_output_chars=raw_cfg.get("max_output_chars", 4000)
            )
            cfg.validate()
            loaded[server_id] = cfg

        self.configs = loaded
        return loaded

    def start_and_bridge_all(self) -> Dict[str, list]:
        configs = self.load_configs()
        results = {}

        for server_id, cfg in configs.items():
            try:
                full_cmd = [cfg.command] + cfg.args
                client = McpClient(
                    command=full_cmd,
                    env=cfg.env,
                    cwd=cfg.cwd,
                    default_timeout=cfg.timeout_seconds
                )
                client.server_name = server_id
                bridge = McpToolBridge(client=client, config=cfg, registry=self.registry)
                bridged_tools = bridge.bridge()

                self.clients[server_id] = client
                results[server_id] = bridged_tools
            except Exception as e:
                # 单个外部服务失败不阻塞整体
                results[server_id] = [f"【启动异常: {str(e)}】"]

        return results

    def close_all(self):
        for server_id, client in list(self.clients.items()):
            try:
                client.close()
            except Exception:
                pass
        self.clients.clear()

default_mcp_manager = McpManager()
