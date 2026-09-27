# -*- coding: utf-8 -*-
"""
tools/policies.py: 命令安全策略与 Human-in-the-Loop 交互审批引擎
针对本地终端 Coding Agent 优化：消除测试与代码审查疲劳，防范复合命令链与换行符逃逸。
"""
import os
import re
from enum import Enum
from typing import Tuple, List, Optional

try:
    from config.settings import APPROVAL_MODE
except Exception:
    APPROVAL_MODE = os.getenv("APPROVAL_MODE", os.getenv("SUPER_APPROVAL_MODE", "auto")).strip().lower()


class PolicyDecision(Enum):
    ALLOW = "allow"             # 安全命令：自动放行（无需打扰用户）
    DENY = "deny"               # 危险命令：强制阻断（不可审批）
    REQUIRE_APPROVAL = "ask"    # 敏感命令：需要人工交互审批 (Human-in-the-Loop)

def _split_shell_commands(command: str) -> List[str]:
    """
    将 Shell 复合命令安全切分为独立的子命令单元，严格忽略引号内部的控制字符。
    支持切分操作符：&&, ||, ;, |, &, 以及换行符 (\r\n, \n, \r)
    """
    tokens = []
    current = []
    in_single = False
    in_double = False
    escape = False
    i = 0
    n = len(command)

    while i < n:
        c = command[i]

        if escape:
            current.append(c)
            escape = False
            i += 1
            continue

        if c == "\\":
            escape = True
            current.append(c)
            i += 1
            continue

        if c == "'" and not in_double:
            in_single = not in_single
            current.append(c)
            i += 1
            continue

        if c == '"' and not in_single:
            in_double = not in_double
            current.append(c)
            i += 1
            continue

        if not in_single and not in_double:
            # 检查换行符切分: \r\n 或 \n, \r
            if command[i:i+2] == "\r\n":
                token = "".join(current).strip()
                if token:
                    tokens.append(token)
                current = []
                i += 2
                continue
            if c in ("\n", "\r"):
                token = "".join(current).strip()
                if token:
                    tokens.append(token)
                current = []
                i += 1
                continue

            # 检查复合逻辑符: &&, ||
            if i + 1 < n and command[i:i+2] in ("&&", "||"):
                token = "".join(current).strip()
                if token:
                    tokens.append(token)
                current = []
                i += 2
                continue
            # 检查单字符分隔符: ;, |, &
            if c in (";", "|", "&"):
                # 关键修复：排除 2>&1, >&, &>, &>> 等标准输出/错误重定向语法中的 & 符号
                if c == "&" and ((i > 0 and command[i-1] == ">") or (i + 1 < n and command[i+1] == ">")):
                    current.append(c)
                    i += 1
                    continue

                token = "".join(current).strip()
                if token:
                    tokens.append(token)
                current = []
                i += 1
                continue

        current.append(c)
        i += 1

    last = "".join(current).strip()
    if last:
        tokens.append(last)

    return tokens or [command.strip()]


class CommandPolicy:
    """
    命令安全策略引擎：在任何 shell 命令下发前进行三级风险评估与决策
    """
    # 1. 绝对禁止黑名单 (DENY)：破坏性、系统级高危、提权或敏感文件窥探
    DENY_PATTERNS = [
        # 破坏性目录与文件删除 (跨平台: Linux rm, Windows cmd rmdir/rd/del/erase, PowerShell Remove-Item)
        r"\b(rmdir|rd)\s+.*(/s|\\s)",
        r"\b(del|erase)\s+.*(/f|/s|/q)",
        r"\brm\s+.*(-rf|-fr|-r\s+-f|-f\s+-r)",
        r"\b(Remove-Item|ri|rm)\b.*(-Recurse|-r)\b.*(-Force|-fo)\b",
        r"\b(format|mkfs)\b",

        # 关机 / 重启
        r"\b(shutdown|reboot)\b",

        # 提权与隐式远程下载执行 (RCE 防护)
        r"\b(curl|wget)\b.*\|\s*(bash|sh|powershell|pwsh)",
        r"\b(irm|Invoke-RestMethod|Invoke-WebRequest)\b.*\|\s*(iex|Invoke-Expression)\b",
        r"\bpowershell\b.*(-enc|-EncodedCommand|-e\b)",
        r"\bcertutil\b.*-urlcache",
        r"\bbitsadmin\b.*\/transfer",

        # 凭据与敏感文件窃取防御 (包括常用只读提取工具与直接重定向读取)
        r"\b(type|cat|more|Get-Content|gc|head|tail|grep|findstr|rg|strings)\b.*(\.env\b|\.env\.local\b|id_rsa\b|id_ed25519\b|id_ecdsa\b|\.git[\\/]config\b)",
        r"<\s*(\.env\b|\.env\.local\b|id_rsa\b|id_ed25519\b|id_ecdsa\b|\.git[\\/]config\b)",
    ]

    # 2. 安全白名单 (ALLOW)：只读查询、状态检测、测试套件、静态分析
    ALLOW_PREFIXES = [
        # Git 只读审查
        "git status",
        "git log",
        "git branch",
        "git diff",
        "git show",
        "git tag",
        "git rev-parse",
        "git describe",

        # Python 测试与语法/风格检查
        "pytest",
        "python -m pytest",
        "python -m unittest",
        "flake8",
        "mypy",
        "ruff check",
        "ruff",
        "pylint",
        "black --check",
        "python -m flake8",
        "python -m mypy",

        # Node / 前端测试与语法检查
        "npm test",
        "npm run test",
        "yarn test",
        "pnpm test",
        "npx eslint",
        "eslint",
        "npm run lint",

        # 其他语言只读与测试
        "cargo test",
        "cargo check",
        "go test",

        # 文本过滤与安全流式工具
        "grep",
        "findstr",
        "head",
        "tail",
        "wc",
        "sort",
        "uniq",

        # 环境与版本只读查询
        "python --version",
        "python -V",
        "pip --version",
        "pip list",
        "pip show",
        "node --version",
        "node -v",
        "npm --version",
        "npm list",
        "cargo --version",
        "go version",
        "dir",
        "ls",
        "echo",
        "pwd",
        "cd",
        "whoami",
    ]

    def __init__(self, mode: Optional[str] = None):
        """
        :param mode: 审批模式
            - 'auto' / 'never': 全自动模式 (类似 Claude AUTO 模式)，非黑名单高危命令均自动放行（默认推荐）
            - 'ask': 敏感命令在终端提示用户输入 [y/n/a]
            - 'always_ask': 严格模式，任何命令都必须人工确认
        """
        if mode is None:
            mode = APPROVAL_MODE
        self.mode = mode if mode in ("auto", "never", "ask", "always_ask") else "auto"
        self.session_approved = False  # 会话级全局信任开关

    def reset_session_approval(self):
        """重置当前会话的临时放行状态"""
        self.session_approved = False

    def _evaluate_atomic_command(self, cmd_clean: str) -> Tuple[PolicyDecision, str]:
        """评估单个原子（不可切分）命令"""
        if not cmd_clean:
            return PolicyDecision.DENY, "子命令为空"

        # 1. 检查黑名单
        for pattern in self.DENY_PATTERNS:
            if re.search(pattern, cmd_clean, re.IGNORECASE):
                return (
                    PolicyDecision.DENY,
                    f"命中高危命令防御黑名单（检测到潜在破坏性特征: '{pattern}'）"
                )

        # 2. 检查命令替换与子 Shell 动态执行语法: $(...), `...`
        if re.search(r"(\$\([^\)]*\)|`[^`]*`)", cmd_clean):
            return (
                PolicyDecision.REQUIRE_APPROVAL,
                f"子命令 '{cmd_clean}' 包含子 Shell 动态命令替换表达式，需人工审批确认"
            )

        # 3. 检查重定向写文件操作: echo/printf 等命令若使用 > 或 >> 写入文件，不可作为只读白名单放行
        cmd_lower = cmd_clean.lower()
        if cmd_lower.startswith("echo ") or cmd_lower == "echo":
            if re.search(r"(?<!2|&)>", cmd_clean):
                return (
                    PolicyDecision.REQUIRE_APPROVAL,
                    f"子命令 '{cmd_clean}' 包含重定向文件写操作，需人工确认"
                )

        # 4. 检查严格词界前缀白名单（消除伪前缀绕过，如 git status_evil）
        for prefix in self.ALLOW_PREFIXES:
            p_lower = prefix.lower()
            if cmd_lower == p_lower or cmd_lower.startswith(p_lower + " ") or cmd_lower.startswith(p_lower + "\t"):
                return PolicyDecision.ALLOW, f"匹配安全白名单: '{prefix}'"

        return (
            PolicyDecision.REQUIRE_APPROVAL,
            f"子命令 '{cmd_clean}' 可能改变环境、读写文件或发起网络请求，需人工确认"
        )

    def evaluate(self, command: str) -> Tuple[PolicyDecision, str]:
        """
        核心策略评估函数：
        深度切分复合命令链 (&&, ||, ;, |, &, \n)，要求链上每一个原子命令均合法。
        核心原则：高危黑名单具有绝对优先级，无论 AUTO 模式或 session_approved 均不得越过黑名单拦截！
        """
        cmd_clean = command.strip()
        if not cmd_clean:
            return PolicyDecision.DENY, "命令为空"

        # 1. 全局前置黑名单扫描（防止复合命令中有整体黑名单模式）
        for pattern in self.DENY_PATTERNS:
            if re.search(pattern, cmd_clean, re.IGNORECASE):
                return (
                    PolicyDecision.DENY,
                    f"命中高危命令防御黑名单（检测到潜在破坏性特征: '{pattern}'）"
                )

        # 2. 深度切分复合命令链
        sub_commands = _split_shell_commands(cmd_clean)

        # 3. 核心安全守卫：无论任何模式或会话是否已信任，只要链上任一子命令命中高危黑名单，必须强制阻断！
        for sub_cmd in sub_commands:
            sub_dec, sub_reason = self._evaluate_atomic_command(sub_cmd)
            if sub_dec == PolicyDecision.DENY:
                return PolicyDecision.DENY, f"复合命令链被阻断：{sub_reason}"

        # 4. 会话级全局信任放行 (仅在所有子命令均无高危破坏行为的前提下)
        if self.session_approved:
            return PolicyDecision.ALLOW, "用户此前已信任当前会话后续所有命令"

        # 5. 全自动模式放行
        if self.mode in ("never", "auto"):
            return PolicyDecision.ALLOW, "Claude 风格 AUTO 模式全自动放行"

        # 6. 严格模式
        if self.mode == "always_ask":
            return PolicyDecision.REQUIRE_APPROVAL, "严格模式：任何命令均须人工审批"

        # 7. 人工审批模式 (ASK): 逐一审查各个原子子命令
        all_reasons = []
        for sub_cmd in sub_commands:
            sub_dec, sub_reason = self._evaluate_atomic_command(sub_cmd)
            if sub_dec == PolicyDecision.REQUIRE_APPROVAL:
                return PolicyDecision.REQUIRE_APPROVAL, f"复合命令包含需审批子命令：{sub_reason}"
            all_reasons.append(sub_reason)

        return PolicyDecision.ALLOW, "复合命令中所有子命令均匹配安全白名单"

    def request_approval(self, command: str, reason: str) -> bool:
        """
        终端交互卡片：Human-in-the-Loop 人工审核
        """
        # 在 AUTO 模式或会话已授权状态下，直接放行，无需终端打扰
        if self.mode in ("auto", "never") or self.session_approved:
            return True

        try:
            from cli.ui import default_ui
            if default_ui.is_active:
                return default_ui.render_approval_prompt(command, reason)
        except Exception:
            pass

        print("\n" + "!" * 55)
        print("【安全提示】Agent 申请执行敏感操作：")
        print(f"  待执行操作:  {command}")
        print(f"  拦截原因:    {reason}")
        print("-" * 55)
        print("请选择操作:")
        print("  [y] 批准本次执行 (Yes)")
        print("  [n] 拒绝本次执行 (No, 默认)")
        print("  [a] 信任并批准本次会话后续所有命令 (Approve All)")
        print("!" * 55)

        while True:
            try:
                choice = input("您的决定 [y/n/a] (默认 n): ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print("\n操作已取消。")
                return False

            if choice in ("y", "yes"):
                return True
            elif choice in ("n", "no", ""):
                return False
            elif choice in ("a", "all"):
                self.session_approved = True
                print(">>> 已开启当前会话后续命令自动放行权限。")
                return True
            else:
                print("输入无效，请输入 y、n 或 a")


# 全局默认单例 (默认采用 Claude 风格 AUTO 自动审批模式)
default_policy = CommandPolicy()
