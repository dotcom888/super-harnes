import json
import logging
from enum import Enum
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class LoopState(Enum):
    NORMAL = "normal"              # 正常执行推进
    WARNING = "warning"            # 黄牌警告：检测到初步停滞或轻度重复
    FORCE_WRAPUP = "force_wrapup"  # 红牌出场：多次连续重复或陷入震荡死循环，强制关闭工具收尾

class LoopDetector:
    """
    智能体轮内死循环与停滞监测引擎 (Loop & Stall Detector):
    负责捕获以下三种典型死循环模式：
    1. 模式 1：连续完全相同工具调用（相同工具名称与参数指纹连续 >= 3 次）
    2. 模式 2：多工具周期性震荡循环（A -> B -> A -> B 周期重复 >= 3 次）
    3. 模式 3：连续相同报错硬撞（同一工具连续出现相同错误返回值 >= 3 次）

    提供两段式自救机制：
    - 阶段 1 (WARNING): 注入反思黄牌警示，引导模型更换工具或修正参数；
    - 阶段 2 (FORCE_WRAPUP): 强制移除 tools 接口，迫使模型汇总已知事实向用户输出最终答复。
    """
    def __init__(
        self,
        max_consecutive_duplicates: int = 3,
        max_cycle_repetitions: int = 3,
        max_repeated_errors: int = 3
    ):
        self.max_consecutive_duplicates = max_consecutive_duplicates
        self.max_cycle_repetitions = max_cycle_repetitions
        self.max_repeated_errors = max_repeated_errors

        # 调用指纹序列: [ "tool_name:sorted_json_args", ... ]
        self.call_history: List[str] = []
        # 返回结果特征序列: [ "tool_name:is_error:result_snippet", ... ]
        self.result_history: List[str] = []
        # 当前检测状态
        self.current_state: LoopState = LoopState.NORMAL
        # 详细诊断原因
        self.diagnosis_reason: str = ""

    def reset(self):
        """重置监测状态（每轮新任务启动时调用）"""
        self.call_history.clear()
        self.result_history.clear()
        self.current_state = LoopState.NORMAL
        self.diagnosis_reason = ""

    @staticmethod
    def _create_call_signature(tool_name: str, args: Any) -> str:
        """生成规范化且唯一的工具调用指纹"""
        clean_name = str(tool_name).strip()
        try:
            if isinstance(args, str):
                args_obj = json.loads(args) if args.strip() else {}
            elif isinstance(args, dict):
                args_obj = args
            else:
                args_obj = str(args)
            sorted_args_str = json.dumps(args_obj, sort_keys=True, ensure_ascii=False)
        except Exception:
            sorted_args_str = str(args).strip()
        return f"{clean_name}:{sorted_args_str}"

    @staticmethod
    def _create_result_signature(tool_name: str, result_content: str) -> str:
        """生成工具返回结果的指纹（区分报错特征）"""
        res_str = str(result_content).strip()
        is_error = (
            res_str.startswith("【安全拦截】")
            or res_str.startswith("【补丁失败】")
            or res_str.startswith("读取失败")
            or res_str.startswith("查看大纲失败")
            or res_str.startswith("Error:")
            or "FileNotFoundError" in res_str
            or "PermissionError" in res_str
            or "未找到 SEARCH 块" in res_str
        )
        snippet = res_str[:120].strip()
        return f"{tool_name}:{is_error}:{snippet}"

    def record_step(self, tool_calls: List[Dict[str, Any]], tool_results: Optional[List[Dict[str, Any]]] = None) -> LoopState:
        """
        记录单步工具调用与返回结果，并执行死循环检测
        """
        if not tool_calls:
            self.current_state = LoopState.NORMAL
            return self.current_state

        # 1. 记录调用指纹（单步可能存在并发 tool_calls，合并为一个复合指纹）
        step_signatures = []
        for tc in tool_calls:
            fn = tc.get("function", {}) if isinstance(tc, dict) else getattr(tc, "function", None)
            fname = fn.get("name", "") if isinstance(fn, dict) else getattr(fn, "name", "")
            fargs = fn.get("arguments", "{}") if isinstance(fn, dict) else getattr(fn, "arguments", "{}")
            sig = self._create_call_signature(fname, fargs)
            step_signatures.append(sig)

        combined_step_sig = " | ".join(sorted(step_signatures))
        self.call_history.append(combined_step_sig)

        # 2. 记录返回结果特征
        if tool_results:
            step_res_sigs = []
            for tr in tool_results:
                content = str(tr.get("content", ""))
                res_sig = self._create_result_signature("tool", content)
                step_res_sigs.append(res_sig)
            self.result_history.append(" | ".join(sorted(step_res_sigs)))

        # 3. 运行检测算法
        state, reason = self._evaluate_loop_patterns()
        self.current_state = state
        self.diagnosis_reason = reason
        return self.current_state

    def _evaluate_loop_patterns(self) -> (LoopState, str):
        """核心评估算法：模式 1、模式 2 与模式 3"""
        n = len(self.call_history)
        if n < 2:
            return LoopState.NORMAL, ""

        # --- 检查模式 1: 连续完全相同工具调用 ---
        current_sig = self.call_history[-1]
        consecutive_count = 0
        for sig in reversed(self.call_history):
            if sig == current_sig:
                consecutive_count += 1
            else:
                break

        if consecutive_count >= self.max_consecutive_duplicates:
            msg = f"检测到连续 {consecutive_count} 步发起完全相同的工具调用与参数: {current_sig[:80]}..."
            logger.warning(f"[死循环熔断] {msg}")
            return LoopState.FORCE_WRAPUP, msg
        elif consecutive_count >= 2:
            msg = f"检测到连续 2 步发起完全相同的工具调用: {current_sig[:80]}..."
            return LoopState.WARNING, msg

        # --- 检查模式 2: 多工具周期性震荡循环 (Period = 2 或 3) ---
        for period in (2, 3):
            if n >= period * 2:
                pattern = self.call_history[-period:]
                cycle_count = 1
                idx = n - period * 2
                while idx >= 0:
                    prev_window = self.call_history[idx:idx + period]
                    if prev_window == pattern:
                        cycle_count += 1
                        idx -= period
                    else:
                        break

                if cycle_count >= self.max_cycle_repetitions:
                    p_desc = " -> ".join([s.split(":")[0] for s in pattern])
                    msg = f"检测到工具调用陷入周期为 {period} 的振荡死循环 (周期重复 {cycle_count} 次): [{p_desc}]"
                    logger.warning(f"[震荡死循环熔断] {msg}")
                    return LoopState.FORCE_WRAPUP, msg
                elif cycle_count == 2:
                    p_desc = " -> ".join([s.split(":")[0] for s in pattern])
                    msg = f"检测到工具调用存在周期为 {period} 的反复振荡倾向: [{p_desc}]"
                    return LoopState.WARNING, msg

        # --- 检查模式 3: 连续相同报错停滞 ---
        m = len(self.result_history)
        if m >= self.max_repeated_errors:
            latest_res = self.result_history[-1]
            if ":True:" in latest_res:  # 属于报错指纹
                repeat_err_count = 0
                for r in reversed(self.result_history):
                    if r == latest_res:
                        repeat_err_count += 1
                    else:
                        break
                if repeat_err_count >= self.max_repeated_errors:
                    msg = f"检测到工具执行连续 {repeat_err_count} 步遭遇完全相同的失败报错，排查已陷入死胡同。"
                    logger.warning(f"[连续报错熔断] {msg}")
                    return LoopState.FORCE_WRAPUP, msg

        return LoopState.NORMAL, ""

    def get_warning_prompt_banner(self) -> str:
        """生成注入给模型的黄牌反思提示"""
        return (
            f"[系统警示 - 停滞干预]: {self.diagnosis_reason}\n"
            "请立即停止无意义的重复调用！请反思：\n"
            "1. 上一步工具的返回结果是否已满足需要，或已明确报错？\n"
            "2. 严禁使用相同参数反复重试同个工具；请更换排查策略、调整参数，或直接基于现有已知事实输出解答。"
        )

    def get_wrapup_prompt_banner(self) -> str:
        """生成注入给模型的红牌强制收尾提示"""
        return (
            f"[系统安全熔断]: {self.diagnosis_reason}\n"
            "【注意: 为防止无限空转，工具调用权限已被强制关闭】\n"
            "请不要再尝试调用任何工具。请基于前序已排查收集到的全部代码事实与报错信息，"
            "向用户全面汇报当前任务的完成进度、遇到的困难阻碍及排查建议。"
        )
