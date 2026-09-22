# -*- coding: utf-8 -*-
"""
tools/builtin/shell_tool.py: 安全受控的终端 Shell 执行工具
集成了 CommandPolicy 权限检查、超时强杀、工作区锁定与输出截断保护。
增强：cwd 参数支持、ANSI 颜色代码清洗、Windows GBK/UTF-8 编码自适应与敏感凭据脱敏。
"""
import os
import re
import locale
import subprocess
from pathlib import Path
from typing import Optional
from tools.registry import register_tool
from tools.framework.policies import default_policy, PolicyDecision, _split_shell_commands
from tools.framework.workspace import default_workspace

# 安全限制参数
DEFAULT_TIMEOUT_SECONDS = 30   # 默认命令超时时间（秒）
MAX_OUTPUT_CHARS = 4000        # 单次最大捕获字符数，避免爆大模型上下文

# 正则：匹配终端 ANSI 颜色与控制转义字符
ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# 环境变量敏感凭证黑名单
SENSITIVE_ENV_KEYS = {
    "LLM_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "GITHUB_TOKEN",
    "GITLAB_TOKEN",
    "HF_TOKEN",
}

# 敏感字段正则匹配（防范第三方 SDK 凭据泄漏）
SENSITIVE_ENV_PATTERN = re.compile(
    r"(?:_KEY|_TOKEN|_SECRET|_PASSWORD|_AUTH|CREDENTIALS|ACCESS_KEY|APIKEY)",
    re.IGNORECASE
)

# 必须保留的系统级基础环境变量
PRESERVED_ENV_KEYS = {
    "PATH", "PATHEXT", "PYTHONPATH", "TEMP", "TMP", "USER", "USERNAME",
    "HOME", "USERPROFILE", "SHELL", "COMSPEC", "SYSTEMROOT", "WINDIR",
    "OS", "COMPUTERNAME", "APPDATA", "LOCALAPPDATA"
}

def _get_sanitized_env() -> dict:
    """隔离主进程环境变量，防止子进程脚本窃取 API Key、Token 等敏感信息"""
    env = os.environ.copy()
    for key in list(env.keys()):
        upper_key = key.upper()
        if upper_key in PRESERVED_ENV_KEYS:
            continue
        if upper_key in SENSITIVE_ENV_KEYS or SENSITIVE_ENV_PATTERN.search(key):
            env.pop(key, None)
    return env

def _strip_ansi(text: str) -> str:
    """去除终端输出中的 ANSI 颜色与控制字符，净化大模型输入"""
    return ANSI_ESCAPE_RE.sub('', text)

def _decode_bytes(raw_bytes: bytes) -> str:
    """
    自适应解码终端原始字节流：
    优先尝试 UTF-8，失败时尝试系统默认编码（Windows 下为 CP936/GBK），消除中文报错乱码。
    """
    if not raw_bytes:
        return ""
    # 1. 优先尝试 UTF-8
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # 2. 回退尝试系统首选编码 (Windows 控制台常为 cp936/gbk)
    try:
        sys_enc = locale.getpreferredencoding(False)
        if sys_enc and sys_enc.lower() not in ("utf-8", "utf8"):
            return raw_bytes.decode(sys_enc)
    except Exception:
        pass

    # 3. 常见中文编码遍历
    for enc in ("gbk", "cp936", "latin1"):
        try:
            return raw_bytes.decode(enc)
        except Exception:
            pass

    # 4. 保底容错解码
    return raw_bytes.decode("utf-8", errors="replace")

def __getattr__(name: str):
    """向后兼容对 WORKSPACE_ROOT 的属性读取"""
    if name == "WORKSPACE_ROOT":
        return default_workspace.root
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

@register_tool(
    name="run_shell",
    description="""在工作区沙箱中执行终端 Shell 命令（如运行测试、git 查询、运行 python 脚本等）。
支持指定子工作目录 cwd；高危破坏性命令将被永久拦截；环境修改或高危操作需用户手动审批。""",
    param_descriptions={
        "command": "要在终端执行的 Shell 命令字符串，例如 'pytest' 或 'git status'",
        "timeout": f"最大执行超时时间（秒），默认为 {DEFAULT_TIMEOUT_SECONDS} 秒，防进程挂起",
        "cwd": "可选的命令执行工作目录（相对工作区根目录或绝对路径），默认为当前工作区根目录"
    }
)
def run_shell(
    command: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    cwd: Optional[str] = None
) -> str:
    """
    带安全审批、动态工作区、环境隔离与编码自适应的 Shell 执行工具
    """
    cmd_clean = command.strip()
    if not cmd_clean:
        return "执行失败: 命令不能为空。"

    # 0. 裸 cd 命令快速拦截与智能引导（仅拦截纯原子 cd，放行如 cd frontend && npm test 等复合命令）
    sub_cmds = _split_shell_commands(cmd_clean)
    if len(sub_cmds) == 1 and re.match(r"^\s*cd(\s+.*)?$", sub_cmds[0], re.IGNORECASE):
        parts = sub_cmds[0].split(None, 1)
        target_dir = parts[1].strip() if len(parts) > 1 else ""
        example_cwd = f"cwd='{target_dir}'" if target_dir else "cwd='xxx'"
        return (
            f"【执行提示】：单次子进程执行 cd 无法持久改变后续命令的工作目录。\n"
            f"如需在子目录执行命令，请在调用 run_shell 时直接传入 cwd 参数（例如：run_shell(command='...', {example_cwd})）；"
            f"或使用复合命令：'{cmd_clean} && <your_command>'。"
        )

    # 1. 策略前置评估 (Command Policy)
    decision, reason = default_policy.evaluate(cmd_clean)

    # 1.1 黑名单绝对阻断
    if decision == PolicyDecision.DENY:
        return f"【安全拦截拒绝】：命令已被系统安全防火墙直接阻断！\n原因: {reason}"

    # 1.2 敏感命令需人工确认 (Human-in-the-Loop)
    if decision == PolicyDecision.REQUIRE_APPROVAL:
        is_approved = default_policy.request_approval(cmd_clean, reason)
        if not is_approved:
            return f"【用户拒绝】：用户在终端取消或拒绝了该命令的执行申请：'{cmd_clean}'。"

    # 2. 计算与校验执行目录 cwd
    workspace_root = default_workspace.root
    effective_cwd = workspace_root
    if cwd:
        try:
            target_cwd = default_workspace.resolve_path(cwd)
            if not target_cwd.exists() or not target_cwd.is_dir():
                return f"执行失败: 指定的执行目录不存在或不是有效目录: '{cwd}'"
            if not default_workspace.is_inside(target_cwd):
                return f"【安全拦截】：指定的执行目录 '{cwd}' 超出了工作区范围 ({workspace_root})。"
            effective_cwd = target_cwd
        except Exception as e:
            return f"执行失败: 解析工作目录失败: {e}"

    safe_timeout = max(1, min(120, int(timeout)))

    try:
        # 3. 隔离凭据，启动子进程执行并捕获原始字节
        process = subprocess.run(
            cmd_clean,
            shell=True,
            cwd=str(effective_cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=safe_timeout,
            env=_get_sanitized_env()
        )

        stdout = _strip_ansi(_decode_bytes(process.stdout))
        stderr = _strip_ansi(_decode_bytes(process.stderr))
        return_code = process.returncode

        # 4. 组装输出并做输出截断（避免撑爆 Token）
        combined_output = ""
        if stdout:
            combined_output += f"[标准输出 (stdout)]:\n{stdout}\n"
        if stderr:
            combined_output += f"[错误输出 (stderr)]:\n{stderr}\n"
        if not combined_output:
            combined_output = "（命令执行完毕，终端无文本输出）\n"



        if len(combined_output) > MAX_OUTPUT_CHARS:
            half = MAX_OUTPUT_CHARS // 2
            combined_output = (
                combined_output[:half]
                + f"\n\n... [中间输出已截断，共省略 {len(combined_output) - MAX_OUTPUT_CHARS} 字符] ...\n\n"
                + combined_output[-half:]
            )

        status_tag = "成功" if return_code == 0 else f"退出码 {return_code}"
        return f"【执行状态: {status_tag}】\n{combined_output}".strip()

    except subprocess.TimeoutExpired:
        return f"【执行超时】：命令执行超过 {safe_timeout} 秒上限，已被系统强制终止以防挂起死锁！"
    except Exception as e:
        return f"【执行异常】：启动子进程失败: {type(e).__name__}: {str(e)}"

