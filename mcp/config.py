# -*- coding: utf-8 -*-
from typing import Dict, List, Optional, Any

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
