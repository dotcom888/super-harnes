# -*- coding: utf-8 -*-
import os
import sys
import json
import collections
import threading
import subprocess
from pathlib import Path
from tools.framework.workspace import default_workspace
from typing import Dict, Any, Optional, List

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# 1. 严格的安全系统环境变量白名单（屏蔽 OPENAI_API_KEY、GITHUB_TOKEN 等敏感凭据）
SAFE_SYSTEM_ENV_KEYS = {
    # 基础与临时目录
    "PATH", "PATHEXT", "TEMP", "TMP", "TMPDIR",
    # Windows 必需运行环境
    "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
    "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "COMMONPROGRAMFILES",
    # POSIX 必需运行环境
    "HOME", "USER", "SHELL", "LANG", "LC_ALL"
}

def get_sanitized_env(custom_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """构建干净的环境变量字典，剥离本地敏感凭据，仅允许白名单系统变量和用户显式声明的变量"""
    clean_env = {k: v for k, v in os.environ.items() if k.upper() in SAFE_SYSTEM_ENV_KEYS}
    clean_env["PYTHONIOENCODING"] = "utf-8"
    if custom_env:
        clean_env.update(custom_env)
    return clean_env

# 2. Windows 平台内核级 Job Object（主进程异常退出或被 Ctrl+C 中断时，由内核强制回收整棵进程树）
class WindowsJobObject:
    def __init__(self):
        self.handle = None
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

                class IO_COUNTERS(ctypes.Structure):
                    _fields_ = [
                        ("ReadOperationCount", ctypes.c_uint64),
                        ("WriteOperationCount", ctypes.c_uint64),
                        ("OtherOperationCount", ctypes.c_uint64),
                        ("ReadTransferCount", ctypes.c_uint64),
                        ("WriteTransferCount", ctypes.c_uint64),
                        ("OtherTransferCount", ctypes.c_uint64),
                    ]

                class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                    _fields_ = [
                        ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                        ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD),
                    ]

                class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                    _fields_ = [
                        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                        ("IoInfo", IO_COUNTERS),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryLimit", ctypes.c_size_t),
                        ("PeakJobMemoryLimit", ctypes.c_size_t),
                    ]

                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
                JobObjectExtendedLimitInformation = 9

                job = kernel32.CreateJobObjectW(None, None)
                if job:
                    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                    res = kernel32.SetInformationJobObject(
                        job,
                        JobObjectExtendedLimitInformation,
                        ctypes.byref(info),
                        ctypes.sizeof(info)
                    )
                    if res:
                        self.handle = job
                    else:
                        kernel32.CloseHandle(job)
            except Exception:
                self.handle = None

    def assign_process(self, proc_handle):
        if self.handle and sys.platform == "win32":
            try:
                import ctypes
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel32.AssignProcessToJobObject(self.handle, proc_handle)
            except Exception:
                pass

    def close(self):
        if self.handle and sys.platform == "win32":
            try:
                import ctypes
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel32.CloseHandle(self.handle)
            except Exception:
                pass
            self.handle = None

class McpClient:
    """
    加固型 MCP 协议 stdio 客户端：
    1. 消除管道死锁：后台守护线程异步持续排空 stderr，杜绝 4KB 匿名管道缓冲区堵死
    2. 进程树管理：结合 Windows Job Object 彻底防止 Ctrl+C 或强杀遗留孤儿僵尸进程
    3. 本地凭据防护：使用系统环境变量白名单，禁止敏感 API Key 静默泄露到第三方服务
    4. 健壮超时与崩溃诊断：带近期诊断日志的精准报错回显
    """
    def __init__(
        self,
        command: list,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        default_timeout: int = 20,
        server_name: str = "mcp"
    ):
        self.command = command
        self.default_timeout = default_timeout
        self.server_name = server_name
        self.is_alive = True
        self._msg_id = 0
        self.job_object = WindowsJobObject()
        self.stderr_history = collections.deque(maxlen=100)

        run_env = get_sanitized_env(env)
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW

        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=run_env,
            cwd=cwd or str(default_workspace.root),
            creationflags=creation_flags
        )

        # 绑定至操作系统内核 Job Object
        if sys.platform == "win32" and hasattr(self.proc, "_handle"):
            self.job_object.assign_process(self.proc._handle)

        # 启动后台守护线程持续排空 stderr，防止 4KB 匿名管道缓冲区填满导致子进程死锁
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()

    def _drain_stderr(self):
        try:
            if self.proc.stderr:
                for line in iter(self.proc.stderr.readline, ""):
                    if not line:
                        break
                    self.stderr_history.append(line)
        except Exception:
            pass

    def _read_line_with_timeout(self, timeout: float) -> str:
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
            raise TimeoutError(f"MCP 服务 '{self.server_name}' 在 {timeout} 秒内未响应，已被超时保护中断。")

        if error:
            raise error[0]

        if not container or not container[0]:
            exit_code = self.proc.poll()
            recent_err = "".join(self.stderr_history)
            self.is_alive = False
            err_msg = f"MCP 服务 '{self.server_name}' 已断开连接 (退出码: {exit_code})。"
            if recent_err.strip():
                err_msg += f"\n[近期服务日志]:\n{recent_err}"
            raise RuntimeError(err_msg)

        return container[0]

    def send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        exit_code = self.proc.poll()
        if exit_code is not None or not self.is_alive:
            self.is_alive = False
            raise RuntimeError(f"MCP Server '{self.server_name}' 进程已终止 (退出码: {exit_code})")

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
            raise RuntimeError(f"向 MCP Server '{self.server_name}' 管道写入请求失败: {e}")

        actual_timeout = timeout if timeout is not None else self.default_timeout
        response_line = self._read_line_with_timeout(actual_timeout)

        try:
            return json.loads(response_line)
        except json.JSONDecodeError as err:
            raise RuntimeError(f"MCP Server '{self.server_name}' 返回了非合法的 JSON-RPC 响应: {response_line[:200]}")

    def close(self):
        """安全终止子进程树并清理句柄资源"""
        self.is_alive = False
        if self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1.5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass

        # 显式关闭标准流管道
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            if stream:
                try:
                    stream.close()
                except Exception:
                    pass

        self.job_object.close()


def __getattr__(name: str):
    if name == "WORKSPACE_ROOT":
        return default_workspace.root
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
