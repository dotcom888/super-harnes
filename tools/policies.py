# -*- coding: utf-8 -*-
"""
tools/policies.py: 命令安全策略与 Human-in-the-Loop 交互审批引擎
"""
import re
from enum import Enum
from typing import Tuple

class PolicyDecision(Enum):
    ALLOW = "allow"             # 安全命令：自动放行（无需打扰用户）
    DENY = "deny"               # 危险命令：强制阻断（不可审批）
    REQUIRE_APPROVAL = "ask"    # 敏感命令：需要人工交互审批 (Human-in-the-Loop)

class CommandPolicy:
    """
    命令安全策略引擎：在任何 shell 命令下发前进行三级风险评估与决策
    """
    # 1. 绝对禁止黑名单 (DENY)：破坏性、系统级高危、提权或敏感文件窥探
    DENY_PATTERNS = [
        # 破坏性删除
        r"\brmdir\s+.*(/s|\\s)",
        r"\brm\s+.*(-rf|-fr|-r\s+-f|-f\s+-r)",
        r"\bdel\s+.*(/f|/s|/q)",
        r"\bformat\b",
        r"\bmkfs\b",
        # 关机 / 重启
        r"\bshutdown\b",
        r"\breboot\b",
        # 提权与隐式下载执行
        r"\bcurl\b.*\|\s*(bash|sh|powershell)",
        r"\bwget\b.*\|\s*(bash|sh|powershell)",
        r"\bpowershell\b.*-enc",
        # 凭据与敏感文件窃取防御
        r"\b(type|cat|more|Get-Content)\b.*\.env\b",
        r"\b(type|cat|more|Get-Content)\b.*id_rsa\b",
    ]

    # 2. 安全白名单 (ALLOW)：只读查询、状态检测、版本检查
    ALLOW_PREFIXES = [
        "git status",
        "git log",
        "git branch",
        "git diff",
        "python --version",
        "python -V",
        "pip --version",
        "pip list",
        "dir",
        "ls",
        "echo",
        "pytest --version",
    ]

    def __init__(self, mode: str = "ask"):
        """
        :param mode: 审批模式
            - 'ask': 敏感命令在终端提示用户输入 [y/n/a]（默认推荐）
            - 'always_ask': 严格模式，任何命令都必须人工确认
            - 'never': 全自动模式，非黑名单均放行（仅用于无人值守测试）
        """
        self.mode = mode
        self.session_approved = False  # 会话级全局信任开关

    def evaluate(self, command: str) -> Tuple[PolicyDecision, str]:
        """
        核心策略评估函数
        :return: (决策枚举 PolicyDecision, 判定原因 reason)
        """
        cmd_clean = command.strip()
        if not cmd_clean:
            return PolicyDecision.DENY, "命令为空"

        # 检查 1: 绝对禁止黑名单
        for pattern in self.DENY_PATTERNS:
            if re.search(pattern, cmd_clean, re.IGNORECASE):
                return (
                    PolicyDecision.DENY,
                    f"命中高危命令防御黑名单（检测到潜在破坏性特征: '{pattern}'）"
                )

        # 检查 2: 会话级信任放行
        if self.session_approved:
            return PolicyDecision.ALLOW, "用户此前已选择 [a] 信任当前会话所有命令"

        if self.mode == "never":
            return PolicyDecision.ALLOW, "全自动模式放行"

        if self.mode == "always_ask":
            return PolicyDecision.REQUIRE_APPROVAL, "严格模式：任何命令均须人工审批"

        # 检查 3: 匹配只读安全白名单
        for prefix in self.ALLOW_PREFIXES:
            if cmd_clean.lower().startswith(prefix.lower()):
                return PolicyDecision.ALLOW, f"匹配只读安全白名单: '{prefix}'"

        # 检查 4: 其余所有带副作用的操作归为敏感操作，触发人工审批
        return (
            PolicyDecision.REQUIRE_APPROVAL,
            "此命令可能改变环境、读写文件或发起网络请求，需人工确认"
        )

    def request_approval(self, command: str, reason: str) -> bool:
        """
        终端交互卡片：Human-in-the-Loop 人工审核
        """
        print("\n" + "!" * 55)
        print("【安全提示】Agent 申请执行终端 Shell 命令：")
        print(f"  待执行命令:  {command}")
        print(f"  拦截原因:    {reason}")
        print("-" * 55)
        print("请选择操作:")
        print("  [y] 批准本次执行 (Yes)")
        print("  [n] 拒绝本次执行 (No)")
        print("  [a] 信任并批准本次会话后续所有命令 (Approve All)")
        print("!" * 55)

        while True:
            try:
                choice = input("您的决定 [y/n/a]: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print("\n操作已取消。")
                return False

            if choice in ("y", "yes"):
                return True
            elif choice in ("n", "no"):
                return False
            elif choice in ("a", "all"):
                self.session_approved = True
                print(">>> 已开启当前会话后续命令自动放行权限。")
                return True
            else:
                print("输入无效，请输入 y、n 或 a")

# 全局默认单例
default_policy = CommandPolicy(mode="ask")