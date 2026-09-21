# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional

class BudgetLedger:
    """
    上下文硬预算账本 (Budget Ledger):
    显式分账总预算，杜绝历史滑窗侵占系统、工具与输出保留区。
    分账明细：
      - 总预算 (Total):           默认 24,000 Tokens
      - 系统提示词 (System):        默认 2,000 Tokens (不可变，保障 Prompt 缓存)
      - 工具定义 (Tools):          默认 2,000 Tokens (工具 Schema 空间)
      - 状态与摘要 (Memory):       默认 2,000 Tokens (WorkingMemory + 历史纪要)
      - 输出预留区 (Output Reserve): 默认 3,000 Tokens (确保模型输出大 Patch / 完整回复不截断)
      - 历史滑动窗口 (History):    动态计算 (total - 各预留)
    """
    def __init__(
        self,
        total_budget: int = 24000,
        system_reserve: int = 2000,
        tools_reserve: int = 2000,
        memory_reserve: int = 2000,
        output_reserve: int = 3000,
        min_history_budget: Optional[int] = None
    ):
        # 严格非负整数参数校验
        for name, val in [
            ("total_budget", total_budget),
            ("system_reserve", system_reserve),
            ("tools_reserve", tools_reserve),
            ("memory_reserve", memory_reserve),
            ("output_reserve", output_reserve),
        ]:
            if not isinstance(val, int) or isinstance(val, bool) or val < 0:
                raise ValueError(f"{name} 必须为非负整数，得到: {val}")

        if total_budget <= 0:
            raise ValueError(f"total_budget 必须大于 0，得到: {total_budget}")

        reserved_sum = system_reserve + tools_reserve + memory_reserve + output_reserve
        if reserved_sum >= total_budget:
            raise ValueError(
                f"预留预算之和 ({reserved_sum}) 不能大于或等于总预算 ({total_budget})"
            )

        # 自适应默认 min_history_budget
        if min_history_budget is None:
            min_history_budget = min(500, max(50, int(total_budget * 0.1)))
        elif not isinstance(min_history_budget, int) or min_history_budget < 0:
            raise ValueError(f"min_history_budget 必须为非负整数，得到: {min_history_budget}")

        self.total_budget = total_budget
        self.system_reserve = system_reserve
        self.tools_reserve = tools_reserve
        self.memory_reserve = memory_reserve
        self.output_reserve = output_reserve
        self.min_history_budget = min_history_budget

        self.history_budget = max(
            min_history_budget,
            total_budget - reserved_sum
        )

    def recalculate_history_budget(
        self,
        actual_system_tokens: Optional[int] = None,
        actual_tools_tokens: Optional[int] = None,
        actual_memory_tokens: Optional[int] = None
    ) -> int:
        """根据实际系统、工具和工作记忆开销动态重算可用历史预算"""
        sys_tokens = self.system_reserve if actual_system_tokens is None else max(0, actual_system_tokens)
        tools_tokens = self.tools_reserve if actual_tools_tokens is None else max(0, actual_tools_tokens)
        mem_tokens = self.memory_reserve if actual_memory_tokens is None else max(0, actual_memory_tokens)

        used_non_history = sys_tokens + tools_tokens + mem_tokens + self.output_reserve
        self.history_budget = max(self.min_history_budget, self.total_budget - used_non_history)
        return self.history_budget

    def get_remaining_budget(self, current_total_tokens: int) -> int:
        """获取当前距离总预算的剩余量"""
        return self.total_budget - current_total_tokens

    def is_over_budget(self, current_total_tokens: int) -> bool:
        """判定是否超出总预算"""
        return current_total_tokens > self.total_budget

    def copy(self) -> "BudgetLedger":
        return BudgetLedger(
            total_budget=self.total_budget,
            system_reserve=self.system_reserve,
            tools_reserve=self.tools_reserve,
            memory_reserve=self.memory_reserve,
            output_reserve=self.output_reserve,
            min_history_budget=self.min_history_budget
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_budget": self.total_budget,
            "system_reserve": self.system_reserve,
            "tools_reserve": self.tools_reserve,
            "memory_reserve": self.memory_reserve,
            "output_reserve": self.output_reserve,
            "history_budget": self.history_budget,
            "min_history_budget": self.min_history_budget
        }

def create_default_budget_ledger() -> BudgetLedger:
    return BudgetLedger()

default_budget_ledger = BudgetLedger()
