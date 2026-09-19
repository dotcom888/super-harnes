# -*- coding: utf-8 -*-

class BudgetLedger:
    """
    上下文硬预算账本 (Budget Ledger):
    显式分账总预算（默认 24,000 Tokens），杜绝历史滑窗侵占系统、工具与输出保留区。
    分账明细：
      - 总预算 (Total):           24,000 Tokens
      - 系统提示词 (System):        2,000 Tokens (不可变，保障 Prompt 缓存)
      - 工具定义 (Tools):          2,000 Tokens (工具 Schema 空间)
      - 状态与摘要 (Memory):       2,000 Tokens (WorkingMemory + 历史纪要)
      - 历史滑动窗口 (History):    15,000 Tokens (实际动态滑窗运算空间)
      - 输出预留区 (Output Reserve): 3,000 Tokens (确保模型输出大 Patch / 完整回复不截断)
    """
    def __init__(
        self,
        total_budget: int = 24000,
        system_reserve: int = 2000,
        tools_reserve: int = 2000,
        memory_reserve: int = 2000,
        output_reserve: int = 3000
    ):
        self.total_budget = total_budget
        self.system_reserve = system_reserve
        self.tools_reserve = tools_reserve
        self.memory_reserve = memory_reserve
        self.output_reserve = output_reserve
        
        # 历史交互真实可用额度 = 24000 - 2000 - 2000 - 2000 - 3000 = 15,000
        self.history_budget = max(
            500,
            total_budget - (system_reserve + tools_reserve + memory_reserve + output_reserve)
        )

    def to_dict(self):
        return {
            "total_budget": self.total_budget,
            "system_reserve": self.system_reserve,
            "tools_reserve": self.tools_reserve,
            "memory_reserve": self.memory_reserve,
            "output_reserve": self.output_reserve,
            "history_budget": self.history_budget
        }

default_budget_ledger = BudgetLedger()
