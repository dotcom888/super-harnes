# -*- coding: utf-8 -*-
import sys
import shutil
from pathlib import Path
from tools.framework.workspace import default_workspace
from typing import Dict, List, Optional, Any

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

class TrustLevel:
    TRUSTED = "trusted"                   # 自动放行 (如纯计算、只读探测)
    REQUIRE_APPROVAL = "require_approval" # 需人工审批 (如网络外联、修改外部数据)
    BLOCKED = "blocked"                   # 黑名单直接拦截

class McpServerConfig:
    """单个 MCP 服务的校验后配置实体"""
    def __init__(
        self,
        server_id: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        trust_level: str = TrustLevel.TRUSTED,
        timeout_seconds: int = 20,
        max_output_chars: int = 4000
    ):
        self.server_id = server_id.strip()
        self.command = command.strip()
        self.args = args or []
        self.env = env or {}
        self.cwd = cwd
        self.trust_level = trust_level.lower() if trust_level in (TrustLevel.TRUSTED, TrustLevel.REQUIRE_APPROVAL, TrustLevel.BLOCKED) else TrustLevel.REQUIRE_APPROVAL
        self.timeout_seconds = max(1, min(120, int(timeout_seconds)))
        self.max_output_chars = max(500, min(20000, int(max_output_chars)))

    def validate(self):
        if not self.server_id:
            raise ValueError("McpServerConfig: server_id 不能为空")
        if not self.command:
            raise ValueError(f"McpServerConfig[{self.server_id}]: command 不能为空")

        agent_home = Path(__file__).resolve().parent.parent

        # 1. 消除 Python 解释器漂移：若指定为 python，强制锁定为当前 Agent 运行的 sys.executable
        cmd_lower = self.command.lower()
        if cmd_lower in ("python", "python3", "python.exe", "python3.exe"):
            self.command = sys.executable
        else:
            resolved = shutil.which(self.command)
            if resolved:
                self.command = resolved
            elif (default_workspace.root / self.command).exists():
                self.command = str((default_workspace.root / self.command).resolve())
            elif (agent_home / self.command).exists():
                self.command = str((agent_home / self.command).resolve())

        # 2. 双基准规范化参数列表中的脚本路径（优先当前工作区，回退 Agent 源码安装目录）
        resolved_args = []
        for arg in self.args:
            path_in_root = default_workspace.root / arg
            path_in_cwd = Path(self.cwd) / arg if self.cwd else None
            path_in_agent = agent_home / arg
            if path_in_root.exists() and path_in_root.is_file():
                resolved_args.append(str(path_in_root.resolve()))
            elif path_in_cwd and path_in_cwd.exists() and path_in_cwd.is_file():
                resolved_args.append(str(path_in_cwd.resolve()))
            elif path_in_agent.exists() and path_in_agent.is_file():
                resolved_args.append(str(path_in_agent.resolve()))
            else:
                resolved_args.append(arg)
        self.args = resolved_args

    @classmethod
    def from_dict(cls, server_id: str, data: Dict[str, Any]) -> "McpServerConfig":
        cfg = cls(
            server_id=server_id,
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", None),
            cwd=data.get("cwd", None),
            trust_level=data.get("trust_level", TrustLevel.TRUSTED),
            timeout_seconds=data.get("timeout_seconds", 20),
            max_output_chars=data.get("max_output_chars", 4000)
        )
        cfg.validate()
        return cfg


def __getattr__(name: str):
    if name == "WORKSPACE_ROOT":
        return default_workspace.root
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
