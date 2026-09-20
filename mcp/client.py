# -*- coding: utf-8 -*-
import os
import sys
import json
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

class McpClient:
    """
    加固型 MCP 协议 stdio 客户端：
    1. 请求硬超时限制 (Timeout Guard)，防止外部服务死锁导致 Agent 挂起；
    2. 子进程意外崩溃检测 (Crash Detection)；
    3. 进程树安全销毁与优雅回收。
    """
    def __init__(
        self,
        command: list,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        default_timeout: int = 20
    ):
        self.command = command
        self.default_timeout = default_timeout
        self.is_alive = True
        self._msg_id = 0

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

    def _read_line_with_timeout(self, timeout: float) -> str:
        """带超时的标准输出读取器 (基于守护线程实现跨平台 Windows 安全超时)"""
        container = []
        error = []

        def reader():
            try:
                line = self.proc.stdout.readline()
                container.append(line)
            except Exception as e:
                error.append(e)

        worker = threading.Thread(target=reader, daemon=True)
        worker.start()
        worker.join(timeout=timeout)

        if worker.is_alive():
            # 外部进程无响应，触发超时
            raise TimeoutError(f"MCP 服务在 {timeout} 秒内未返回响应，已被超时守卫拦截。")

        if error:
            raise error[0]

        if not container or not container[0]:
            exit_code = self.proc.poll()
            err_output = self.proc.stderr.read() if self.proc.stderr else ""
            self.is_alive = False
            raise RuntimeError(f"MCP 服务已断开或崩溃 (退出码: {exit_code})。错误输出: {err_output}")

        return container[0]

    def send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """向外部 Server 发送一条 JSON-RPC 请求，具备超时与崩溃保护"""
        exit_code = self.proc.poll()
        if exit_code is not None:
            self.is_alive = False
            raise RuntimeError(f"MCP Server 进程已处于终止状态 (退出码: {exit_code})")

        self._msg_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._msg_id,
            "method": method,
            "params": params or {}
        }

        try:
            req_json = json.dumps(payload, ensure_ascii=False) + "\n"
            self.proc.stdin.write(req_json)
            self.proc.stdin.flush()
        except Exception as e:
            self.is_alive = False
            raise RuntimeError(f"向 MCP Server 管道写入请求失败: {e}")

        # 读取响应（受超时限制保护）
        actual_timeout = timeout if timeout is not None else self.default_timeout
        response_line = self._read_line_with_timeout(actual_timeout)

        try:
            return json.loads(response_line)
        except json.JSONDecodeError as err:
            raise RuntimeError(f"MCP Server 返回了非合法的 JSON-RPC 响应: {response_line[:200]}")

    def close(self):
        """安全终止外部服务子进程"""
        if self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.is_alive = False
