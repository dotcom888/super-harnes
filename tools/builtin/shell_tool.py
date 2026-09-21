# -*- coding: utf-8 -*-
"""
tools/shell_tool.py: 安全受控的终端 Shell 执行工具
集成了 CommandPolicy 权限检查、超时强杀、工作区锁定与输出截断保护。
"""
import subprocess
from pathlib import Path
from tools.registry import register_tool
from tools.policies import default_policy, PolicyDecision

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

# 安全限制参数
DEFAULT_TIMEOUT_SECONDS = 30   # 默认命令超时时间（秒）
MAX_OUTPUT_CHARS = 4000        # 单次最大捕获字符数，避免爆大模型上下文

@register_tool(
    name="run_shell",
    description="""在受限的工作区沙箱中执行终端 Shell 命令（如运行测试、git 查询、运行 python 脚本等）。
注意：高危破坏性命令将被永久拦截；环境修改或执行类命令需要用户在控制台手动审批后方可运行。""",
    param_descriptions={
        "command": "要在终端执行的 Shell 命令字符串，例如 'python -m unittest' 或 'git status'",
        "timeout": f"最大执行超时时间（秒），默认为 {DEFAULT_TIMEOUT_SECONDS} 秒，防进程挂起"
    }
)
def run_shell(command: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    """
    带安全审批与沙箱防护的 Shell 执行工具
    """
    cmd_clean = command.strip()
    if not cmd_clean:
        return "执行失败: 命令不能为空。"

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

    # 2. 安全环境准备与参数约束
    safe_timeout = max(1, min(120, int(timeout)))

    try:
        # 3. 在工作区沙箱目录下启动子进程执行
        process = subprocess.run(
            cmd_clean,
            shell=True,
            cwd=str(WORKSPACE_ROOT),      # 强制工作目录锁定在项目根目录
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=safe_timeout,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        stdout = process.stdout or ""
        stderr = process.stderr or ""
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