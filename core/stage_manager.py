# -*- coding: utf-8 -*-
"""
core/stage_manager.py: 基于任务状态机的分阶段工具引导与动态掩码机制 (Stage-Aware Tool Masking)
将 Agent 任务生命周期解耦为三阶段状态机：
1. EXPLORE (探索排查态): 搜寻文件、全文检索、阅读大纲、定向切片阅读
2. MODIFY  (编码实施态): 局部精准修改 apply_patch、新建文件 write_file
3. VERIFY  (验证闭环态): 审查 diff、运行测试 pytest、终端构建验证
支持：
- 基于工具执行反馈的自主状态迁移 (Self-Driving State Transitions)
- 动态 Schema 优先级重排 (Dynamic Priority Reordering, 提升 LLM 关注度)
- 可选的严格阶段工具掩码 (Strict Stage Masking)
- 阶段提示词动态 Banner 注入 (Stage-Aware Prompt Steering)
"""
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Set

class TaskStage(str, Enum):
    EXPLORE = "EXPLORE"   # 探索排查态
    MODIFY = "MODIFY"     # 编码实施态
    VERIFY = "VERIFY"     # 验证闭环态
    GENERAL = "GENERAL"   # 全局通用态

EXPLORE_TOOLS: Set[str] = {"find_by_name", "grep_text", "view_file_outline", "read_file", "list_files"}
MODIFY_TOOLS: Set[str] = {"apply_patch", "write_file"}
VERIFY_TOOLS: Set[str] = {"run_shell"}

STAGE_BANNER_MAP: Dict[TaskStage, str] = {
    TaskStage.EXPLORE: "【当前任务阶段: 探索排查态 (EXPLORE)】优先使用 find_by_name / grep_text / view_file_outline 定位目标代码，锁定后再定向切片查阅。",
    TaskStage.MODIFY: "【当前任务阶段: 编码实施态 (MODIFY)】优先使用 apply_patch 进行最小侵入式修改；严禁使用 write_file 覆写已有大文件。",
    TaskStage.VERIFY: "【当前任务阶段: 验证闭环态 (VERIFY)】代码已修改完成，请优先调用 run_shell(command='git diff') 审查变更，并执行 pytest / 构建命令进行闭环验证！",
    TaskStage.GENERAL: "【当前任务阶段: 综合决策态】根据当前实际上下文灵活调度工具。"
}

class StageManager:
    """Agent 任务阶段状态管理器"""

    def __init__(self, enable_stage_masking: bool = False, initial_stage: TaskStage = TaskStage.EXPLORE):
        self.enable_stage_masking = enable_stage_masking
        self.current_stage = initial_stage
        self.history_transitions: List[Tuple[str, TaskStage]] = []

    def reset(self, initial_stage: TaskStage = TaskStage.EXPLORE):
        """重置状态机为初始阶段"""
        self.current_stage = initial_stage
        self.history_transitions.clear()

    def update_from_tool_call(self, tool_name: str, args: Optional[Dict[str, Any]] = None, result: str = ""):
        """根据工具执行结果自动驱动阶段迁移"""
        norm_tool = (tool_name or "").lower()

        # 1. 刚刚成功修改了代码 -> 立即转入 VERIFY 验证阶段
        if norm_tool in ("apply_patch", "write_file"):
            if any(k in result for k in ["成功应用补丁", "成功写入文件", "成功覆盖写入", "Applied patch"]):
                self._transition_to(TaskStage.VERIFY, reason=f"代码已由 {norm_tool} 修改")
                return

        # 2. 在验证阶段执行了 shell 命令
        if norm_tool == "run_shell":
            # 如果命令失败或测试未通过 -> 返回探索排查或修改阶段
            if any(k in result for k in ["FAILURES", "FAILED", "AssertionError", "error:", "退出码", "【执行异常】"]):
                self._transition_to(TaskStage.EXPLORE, reason="Shell执行/测试报错，转入排查修复")
            elif "成功" in result or "passed" in result.lower():
                # 验证通过，保持在 VERIFY
                self._transition_to(TaskStage.VERIFY, reason="测试/验证通过")
            return

        # 3. 如果在阅读/检索大纲 -> 处于 EXPLORE 阶段
        if norm_tool in EXPLORE_TOOLS:
            if self.current_stage != TaskStage.VERIFY:
                self._transition_to(TaskStage.EXPLORE, reason=f"正在调用 {norm_tool} 查阅代码")

    def _transition_to(self, new_stage: TaskStage, reason: str = ""):
        if new_stage != self.current_stage:
            self.history_transitions.append((reason, new_stage))
            self.current_stage = new_stage

    def reorder_or_mask_schemas(self, schemas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        根据当前任务阶段对工具列表进行智能重排或阶段掩码：
        - 若开启 enable_stage_masking: 仅暴露当前阶段工具 + 只读探查工具
        - 若未开启 (默认): 将当前阶段的核心工具置顶，提升大模型的 Attention 权重
        """
        if not schemas:
            return schemas

        if self.current_stage == TaskStage.EXPLORE:
            priority_order = ["find_by_name", "grep_text", "view_file_outline", "read_file", "list_files"]
        elif self.current_stage == TaskStage.MODIFY:
            priority_order = ["apply_patch", "write_file", "read_file", "view_file_outline"]
        elif self.current_stage == TaskStage.VERIFY:
            priority_order = ["run_shell", "read_file", "view_file_outline"]
        else:
            priority_order = ["find_by_name", "grep_text", "view_file_outline", "read_file", "run_shell"]

        priority_tools = set(priority_order)

        if self.enable_stage_masking:
            # 严格掩码模式：仅保留优先级工具和只读探索工具
            allowed_tools = priority_tools | EXPLORE_TOOLS
            filtered = [
                s for s in schemas
                if s.get("function", {}).get("name") in allowed_tools or s.get("function", {}).get("name", "").startswith("mcp__")
            ]
            filtered.sort(key=lambda s: priority_order.index(s.get("function", {}).get("name")) if s.get("function", {}).get("name") in priority_order else 999)
            return filtered if filtered else schemas

        # 优先级重排模式 (默认): 核心工具按 priority_order 权重置顶，其余工具紧随其后
        top_schemas = []
        other_schemas = []
        for s in schemas:
            fname = s.get("function", {}).get("name", "")
            if fname in priority_tools:
                top_schemas.append(s)
            else:
                other_schemas.append(s)

        top_schemas.sort(key=lambda s: priority_order.index(s.get("function", {}).get("name")) if s.get("function", {}).get("name") in priority_order else 999)
        return top_schemas + other_schemas

    def get_stage_banner(self) -> str:
        """获取当前阶段的动态提示词 Banner"""
        return STAGE_BANNER_MAP.get(self.current_stage, STAGE_BANNER_MAP[TaskStage.GENERAL])
