# -*- coding: utf-8 -*-
import json
import concurrent.futures
from pathlib import Path
from tools.framework.workspace import default_workspace
from typing import Dict, Any, Optional, Callable, List, Union
from mcp.client import McpClient
from mcp.config import McpServerConfig, TrustLevel
from mcp.bridge import McpToolBridge
from tools.framework.registry import ToolRegistry, default_registry

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
AGENT_INSTALL_ROOT = Path(__file__).resolve().parent.parent

class McpManager:
    """
    加固型 MCP 服务管理器：
    1. 并行并发握手：使用多线程并行启动多个外部子进程，消除单点慢服务阻塞整个 CLI 启动
    2. 进程树生命周期统一管控与退出清理
    3. 异常即时自愈：握手或加载失败时立即主动销毁失败进程，防止会话期孤儿僵死进程泄漏
    4. 异常隔离：单个外部服务启动失败或超时不影响其他服务
    """
    def __init__(self, config_path: Optional[str] = None, registry: ToolRegistry = default_registry):
        self._custom_config_path = Path(config_path) if config_path else None

        self.registry = registry
        self.clients: Dict[str, McpClient] = {}
        self.configs: Dict[str, McpServerConfig] = {}
        self.loaded_config_paths: List[Path] = []


    @property
    def config_path(self) -> Path:
        """获取当前工作区首选绑定的 MCP 配置文件路径（向后兼容工作区感知单测）"""
        if self._custom_config_path:
            return self._custom_config_path
        preferred = default_workspace.root / "config" / "mcp_servers.json"
        return preferred if preferred.exists() else (default_workspace.root / "mcp_servers.json")

    @config_path.setter
    def config_path(self, path: Union[str, Path, None]):
        self._custom_config_path = Path(path) if path else None

    def get_candidate_config_paths(self) -> List[Path]:
        """
        获取多层级级联候选路径列表（按优先级从高到低）：
        1. 目标工程项目专属配置：<workspace>/.super/mcp_servers.json、<workspace>/config/mcp_servers.json、<workspace>/mcp_servers.json
        2. 用户全局配置：~/.super-harnes/mcp_servers.json
        3. Agent 安装包内置保底配置：<agent_home>/config/mcp_servers.json、<agent_home>/mcp_servers.json
        """
        candidates: List[Path] = [
            default_workspace.root / ".super" / "mcp_servers.json",
            default_workspace.root / "config" / "mcp_servers.json",
            default_workspace.root / "mcp_servers.json",
            Path.home() / ".super-harnes" / "mcp_servers.json",
            AGENT_INSTALL_ROOT / "config" / "mcp_servers.json",
            AGENT_INSTALL_ROOT / "mcp_servers.json"
        ]
        unique_candidates: List[Path] = []
        seen = set()
        for p in candidates:
            try:
                resolved = p.resolve()
            except Exception:
                resolved = p
            if resolved not in seen:
                seen.add(resolved)
                unique_candidates.append(p)
        return unique_candidates

    def load_configs(self) -> Dict[str, McpServerConfig]:
        """
        加载并合并 MCP 服务配置：
        若显式指定了 custom_config_path，仅读取该文件；
        否则按三级级联由底向上（内置保底 -> 用户全局 -> 项目专属）加载并合并，高优先级配置覆盖低优先级。
        """
        if self._custom_config_path:
            if not self._custom_config_path.exists():
                return {}
            target_files = [self._custom_config_path]
        else:
            existing = [p for p in self.get_candidate_config_paths() if p.exists()]
            if not existing:
                return {}
            # 反转：低优先级先放入字典，高优先级（项目专属）后放入实现覆盖
            target_files = list(reversed(existing))

        merged_servers: Dict[str, Dict[str, Any]] = {}
        valid_loaded_paths: List[Path] = []
        for cfg_file in target_files:
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                servers = data.get("mcpServers", {})
                if isinstance(servers, dict):
                    merged_servers.update(servers)
                    if cfg_file not in valid_loaded_paths:
                        valid_loaded_paths.append(cfg_file)
            except Exception as e:
                pass
        self.loaded_config_paths = valid_loaded_paths

        loaded = {}
        for server_id, raw_cfg in merged_servers.items():
            try:
                cfg = McpServerConfig(
                    server_id=server_id,
                    command=raw_cfg.get("command", ""),
                    args=raw_cfg.get("args", []),
                    env=raw_cfg.get("env"),
                    cwd=raw_cfg.get("cwd") or str(default_workspace.root),
                    trust_level=raw_cfg.get("trust_level", TrustLevel.TRUSTED),
                    timeout_seconds=raw_cfg.get("timeout_seconds", 20),
                    max_output_chars=raw_cfg.get("max_output_chars", 4000)
                )
                cfg.validate()
                loaded[server_id] = cfg
            except Exception as e:
                pass

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
        try:
            bridge = McpToolBridge(client=client, config=cfg, registry=self.registry)
            bridged_tools = bridge.bridge()
            self.clients[server_id] = client
            return bridged_tools
        except Exception:
            # 关键防御：握手或枚举工具失败时，立即就地释放并彻底销毁子进程与管道，严防会话期僵死进程遗留
            client.close()
            raise

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


def __getattr__(name: str):
    if name == "WORKSPACE_ROOT":
        return default_workspace.root
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

