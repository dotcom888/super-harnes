# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional, List
import os

DEFAULT_EXPANSION_TIERS = [200000, 250000, 350000, 500000]

class BudgetLedger:
    """
    上下文硬预算账本与动态弹性扩容账本 (Elastic Budget Ledger):
    支持 200k 基准上下文与 250k ~ 500k 按需动态弹性扩展阶梯。
    分账明细：
      - 总预算 (Total):           默认 200,000 Tokens (基线 Tier 0，支持环境变量 AGENT_TOTAL_BUDGET)
      - 弹性梯队 (Tiers):          [200k, 250k, 350k, 500k]，高水位按需自动向上跃迁，低水位防抖冷却缩容
      - 系统提示词 (System):        默认 4,000 Tokens (不可变，保障 Prompt 缓存稳态)
      - 工具定义 (Tools):          默认 6,000 Tokens (工具 Schema 与 MCP 空间)
      - 状态与摘要 (Memory):       默认 6,000 Tokens (WorkingMemory + 历史纪要)
      - 输出预留区 (Output Reserve): 默认 8,000 Tokens (确保模型输出大 Patch / 完整回复不截断)
      - 历史滑动窗口 (History):    动态计算 (total - 各预留，200k 基线提供 176,000 Tokens 广阔滑窗)
    """
    def __init__(
        self,
        total_budget: Optional[int] = None,
        system_reserve: Optional[int] = None,
        tools_reserve: Optional[int] = None,
        memory_reserve: Optional[int] = None,
        output_reserve: Optional[int] = None,
        min_history_budget: Optional[int] = None,
        base_budget: Optional[int] = None,
        max_expand_budget: Optional[int] = None,
        auto_expand: Optional[bool] = None,
        expansion_tiers: Optional[List[int]] = None,
        cooling_turns: int = 2
    ):
        if total_budget is None:
            total_budget = int(os.getenv("AGENT_TOTAL_BUDGET", "200000"))

        if system_reserve is None:
            if total_budget >= 200000:
                system_reserve = 4000
            elif total_budget >= 64000:
                system_reserve = 3000
            elif total_budget >= 8000:
                system_reserve = 2000
            else:
                system_reserve = max(10, int(total_budget * 0.05))

        if tools_reserve is None:
            if total_budget >= 200000:
                tools_reserve = 6000
            elif total_budget >= 64000:
                tools_reserve = 3000
            elif total_budget >= 8000:
                tools_reserve = 2000
            else:
                tools_reserve = max(10, int(total_budget * 0.05))

        if memory_reserve is None:
            if total_budget >= 200000:
                memory_reserve = 6000
            elif total_budget >= 64000:
                memory_reserve = 3000
            elif total_budget >= 8000:
                memory_reserve = 2000
            else:
                memory_reserve = max(10, int(total_budget * 0.05))

        if output_reserve is None:
            if total_budget >= 200000:
                output_reserve = 8000
            elif total_budget >= 64000:
                output_reserve = 4000
            elif total_budget >= 8000:
                output_reserve = 3000
            else:
                output_reserve = max(20, int(total_budget * 0.1))

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
            if total_budget >= 200000:
                min_history_budget = min(5000, max(50, int(total_budget * 0.05)))
            else:
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

        # 弹性阶梯与动态扩容配置
        if base_budget is None:
            env_base = os.getenv("AGENT_BASE_BUDGET")
            base_budget = int(env_base) if env_base else total_budget
        base_budget = min(base_budget, total_budget)

        if max_expand_budget is None:
            env_max = os.getenv("AGENT_MAX_EXPAND_BUDGET")
            max_expand_budget = int(env_max) if env_max else max(500000, total_budget)
        if max_expand_budget < base_budget:
            max_expand_budget = base_budget

        if auto_expand is None:
            auto_expand = os.getenv("AGENT_AUTO_EXPAND", "true").lower() in ("true", "1", "yes")

        # 保护性防扰动：若传入小微测试预算 (如 200, 300, 500, 1000) 且未显式指定梯队与环境变量，默认关闭自动扩展
        if total_budget < 10000 and expansion_tiers is None and "AGENT_AUTO_EXPAND" not in os.environ:
            auto_expand = False
            max_expand_budget = total_budget

        if expansion_tiers is not None:
            cleaned_tiers = sorted(list(set([t for t in expansion_tiers if isinstance(t, int) and t > 0])))
            if base_budget not in cleaned_tiers:
                cleaned_tiers.insert(0, base_budget)
                cleaned_tiers.sort()
            self.expansion_tiers = cleaned_tiers
        else:
            if max_expand_budget <= base_budget:
                self.expansion_tiers = [base_budget]
            else:
                candidates = [t for t in DEFAULT_EXPANSION_TIERS if base_budget <= t <= max_expand_budget]
                if not candidates or candidates[0] != base_budget:
                    candidates.insert(0, base_budget)
                if candidates[-1] != max_expand_budget:
                    candidates.append(max_expand_budget)
                self.expansion_tiers = sorted(list(set(candidates)))

        if total_budget in self.expansion_tiers:
            self.current_tier_index = self.expansion_tiers.index(total_budget)
        else:
            self.expansion_tiers.append(total_budget)
            self.expansion_tiers.sort()
            self.current_tier_index = self.expansion_tiers.index(total_budget)

        self.base_budget = base_budget
        self.max_expand_budget = max_expand_budget
        self.auto_expand = auto_expand
        self.cooling_turns = max(1, cooling_turns)
        self.consecutive_low_turns = 0

    @property
    def is_expanded(self) -> bool:
        """判定当前是否处于弹性扩容状态 (高于基线)"""
        return self.current_tier_index > 0

    def step_up_tier(self) -> bool:
        """单步向上跃迁至下一弹性梯队"""
        if not self.auto_expand or self.current_tier_index >= len(self.expansion_tiers) - 1:
            return False
        self.current_tier_index += 1
        self.total_budget = self.expansion_tiers[self.current_tier_index]
        self.consecutive_low_turns = 0
        self.recalculate_history_budget()
        return True

    def expand_if_needed(self, current_tokens: int, threshold_ratio: float = 0.85) -> bool:
        """
        当 token 消耗达到当前梯队的阈值 (默认 85%) 时，自动向上扩容至更高梯队。
        支持多级连跳（例如单轮突发激增时直接跨级扩容）。
        """
        if not self.auto_expand or self.current_tier_index >= len(self.expansion_tiers) - 1:
            return False

        expanded = False
        while self.current_tier_index < len(self.expansion_tiers) - 1:
            threshold = int(self.total_budget * threshold_ratio)
            if current_tokens >= threshold:
                if self.step_up_tier():
                    expanded = True
                else:
                    break
            else:
                break
        return expanded

    def cooldown_and_contract(self, current_tokens: int, lower_ratio: float = 0.70) -> bool:
        """
        防抖冷却缩容机制：
        当连续 N 轮 (默认 2 轮) 消耗低于上一梯队的 70% 水位时，安全降阶回退一级。
        """
        if not self.auto_expand or self.current_tier_index <= 0:
            self.consecutive_low_turns = 0
            return False

        prev_tier_budget = self.expansion_tiers[self.current_tier_index - 1]
        if current_tokens < int(prev_tier_budget * lower_ratio):
            self.consecutive_low_turns += 1
            if self.consecutive_low_turns >= self.cooling_turns:
                self.current_tier_index -= 1
                self.total_budget = self.expansion_tiers[self.current_tier_index]
                self.consecutive_low_turns = 0
                self.recalculate_history_budget()
                return True
        else:
            self.consecutive_low_turns = 0
        return False

    def reset_to_base(self):
        """重置回滚至基线梯队 (Tier 0)"""
        self.current_tier_index = 0
        self.total_budget = self.expansion_tiers[0]
        self.consecutive_low_turns = 0
        self.recalculate_history_budget()

    def get_tier_info(self) -> Dict[str, Any]:
        """获取当前弹性梯队详细视图"""
        return {
            "base_budget": self.base_budget,
            "max_expand_budget": self.max_expand_budget,
            "current_budget": self.total_budget,
            "current_tier_index": self.current_tier_index,
            "total_tiers": len(self.expansion_tiers),
            "expansion_tiers": list(self.expansion_tiers),
            "is_expanded": self.is_expanded,
            "tier_name": f"Tier {self.current_tier_index} ({self.total_budget // 1000}k)",
            "auto_expand": self.auto_expand,
            "consecutive_low_turns": self.consecutive_low_turns,
            "cooling_turns": self.cooling_turns
        }

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
        cloned = BudgetLedger(
            total_budget=self.total_budget,
            system_reserve=self.system_reserve,
            tools_reserve=self.tools_reserve,
            memory_reserve=self.memory_reserve,
            output_reserve=self.output_reserve,
            min_history_budget=self.min_history_budget,
            base_budget=self.base_budget,
            max_expand_budget=self.max_expand_budget,
            auto_expand=self.auto_expand,
            expansion_tiers=list(self.expansion_tiers),
            cooling_turns=self.cooling_turns
        )
        cloned.current_tier_index = self.current_tier_index
        cloned.consecutive_low_turns = self.consecutive_low_turns
        return cloned

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_budget": self.total_budget,
            "system_reserve": self.system_reserve,
            "tools_reserve": self.tools_reserve,
            "memory_reserve": self.memory_reserve,
            "output_reserve": self.output_reserve,
            "history_budget": self.history_budget,
            "min_history_budget": self.min_history_budget,
            "base_budget": self.base_budget,
            "max_expand_budget": self.max_expand_budget,
            "auto_expand": self.auto_expand,
            "current_tier_index": self.current_tier_index,
            "is_expanded": self.is_expanded,
            "expansion_tiers": list(self.expansion_tiers)
        }

def create_default_budget_ledger() -> BudgetLedger:
    return BudgetLedger()

default_budget_ledger = BudgetLedger()
