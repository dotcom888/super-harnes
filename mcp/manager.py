# -*- coding: utf-8 -*-
import json
import concurrent.futures
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from mcp.client import McpClient
from mcp.config import McpServerConfig, TrustLevel
from mcp.bridge import McpToolBridge
from tools.framework.registry import ToolRegistry, default_registry

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

class McpManager:
    """
    加固型 MCP 服务管理器：
    1. 并行并发握手：使用多线程并行启动多个外部子进程，消除单点慢服务阻塞整个 CLI 启动
    2. 进程树生命周期统一管控与退出清理
    3. 异常隔离：单个外部服务启动失败或超时不影响其他服务
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

    def _start_single_server(self, server_id: str, cfg: McpServerConfig) -> List[str]:
        full_cmd = [cfg.command] + cfg.args
        client = McpClient(
            command=full_cmd,
            env=cfg.env,
            cwd=cfg.cwd,
            default_timeout=cfg.timeout_seconds,
            server_name=server_id
        )
        bridge = McpToolBridge(client=client, config=cfg, registry=self.registry)
        bridged_tools = bridge.bridge()
        self.clients[server_id] = client
        return bridged_tools

    def start_and_bridge_all(self, progress_callback: Optional[Callable[[str, str], None]] = None) -> Dict[str, list]:
        configs = self.load_configs()
        results = {}
        if not configs:
            return results

        # 采用并行多线程连接，彻底避免串行等待带来的白屏假死
        max_workers = min(8, max(1, len(configs)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_server = {
                pool.submit(self._start_single_server, s_id, cfg): s_id
                for s_id, cfg in configs.items()
            }
            for future in concurrent.futures.as_completed(future_to_server):
                server_id = future_to_server[future]
                try:
                    tools = future.result()
                    results[server_id] = tools
                    if progress_callback:
                        progress_callback(server_id, f"就绪 ({len(tools)} 个工具)")
                except Exception as e:
                    results[server_id] = [f"启动失败: {str(e)}"]
                    if progress_callback:
                        progress_callback(server_id, f"失败: {str(e)}")

        return results

    def close_all(self):
        for server_id, client in list(self.clients.items()):
            try:
                client.close()
            except Exception:
                pass
        self.clients.clear()

default_mcp_manager = McpManager()
