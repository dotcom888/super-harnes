# -*- coding: utf-8 -*-
import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

class McpClient:
    """
    标准 MCP 协议 stdio 客户端：
    负责通过管道拉起子进程 MCP Server，并进行标准 JSON-RPC 2.0 异步/同步收发。
    """
    def __init__(self, command: list, env: Optional[Dict[str, str]] = None, cwd: Optional[str] = None):
        self.command = command
        run_env = os.environ.copy()
        run_env["PYTHONIOENCODING"] = "utf-8"
        if env:
            run_env.update(env)

        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=run_env,
            cwd=cwd or str(WORKSPACE_ROOT)
        )
        self._msg_id = 0

    def send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """向外部 Server 发送一条 JSON-RPC 请求并等待返回"""
        if self.proc.poll() is not None:
            raise RuntimeError(f"MCP Server 进程已意外退出，退出码: {self.proc.returncode}")

        self._msg_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._msg_id,
            "method": method,
            "params": params or {}
        }

        req_json = json.dumps(payload, ensure_ascii=False) + "\n"
        self.proc.stdin.write(req_json)
        self.proc.stdin.flush()

        response_line = self.proc.stdout.readline()
        if not response_line:
            err_msg = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"MCP Server 未返回任何响应。Stderr: {err_msg}")

        return json.loads(response_line)

    def close(self):
        """优雅关闭外部服务子进程"""
        if self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
