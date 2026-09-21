# -*- coding: utf-8 -*-
import os
import re
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set
from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

from context.token_counter import TokenCounter, default_token_counter
from context.window import TurnChunk, SlidingWindow
from context.summarizer import ContextSummarizer, SummaryState
from context.budget import BudgetLedger, default_budget_ledger

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = WORKSPACE_ROOT / "history"

class WatermarkZone:
    GREEN = "GREEN"    # < 60%: 全量直通
    YELLOW = "YELLOW"  # 60% ~ 75%: 正常滑动窗口淘汰
    RED = "RED"        # >= 75%: 触发 Summary Compaction (带防抖与区间记录)


class WorkingMemory:
    """
    工作区感知状态：锁定保留，不随滑窗淘汰。
    追踪当前协同目标、关键排查文件、已修改文件与最新测试状态。
    """
    def __init__(self):
        self.current_goal: str = ""
        self.inspected_files: Dict[str, str] = {}
        self.modified_files: List[str] = []
        self.last_test_status: Optional[str] = None

    def update_goal(self, goal: str):
        if goal and str(goal).strip():
            self.current_goal = str(goal).strip()

    def update_from_tool(self, tool_name: str, args: Dict[str, Any], result: str):
        """解析并记录工具对工作区状态的改变，支持内置与通用文件/终端工具"""
        if not isinstance(args, dict):
            return

        # 1. 读文件排查
        if tool_name in ["read_file", "view_file"]:
            filepath = args.get("file_path") or args.get("path") or ""
            start = args.get("start_line", 1)
            max_lines = args.get("max_lines", 100)
            if filepath:
                self.inspected_files[str(filepath)] = f"第 {start} 至 {int(start) + int(max_lines) - 1} 行"

        # 2. 修改文件感知 (apply_patch, write_file, edit_file)
        elif tool_name == "apply_patch":
            patch_content = args.get("patch_content", "")
            created = re.findall(r"\*\*\*\s*(?:Create|Add)\s*File:\s*([^\n]+)", patch_content)
            updated = re.findall(r"\*\*\*\s*Update\s*File:\s*([^\n]+)", patch_content)
            diff_files = re.findall(r"diff --git a/[^\s]+ b/([^\s]+)", patch_content)
            for f in created + updated + diff_files:
                f_clean = f.strip()
                if f_clean and f_clean not in self.modified_files:
                    self.modified_files.append(f_clean)

        elif tool_name in ["write_file", "create_file"]:
            filepath = args.get("file_path") or args.get("path")
            if filepath and str(filepath) not in self.modified_files:
                self.modified_files.append(str(filepath).strip())

        # 3. 命令行与测试感知
        elif tool_name in ["run_shell", "execute_command", "bash"]:
            cmd = args.get("command") or args.get("cmd") or ""
            res_str = str(result) if result else ""
            lines = [l.strip() for l in res_str.splitlines() if l.strip()]
            first_line = lines[0] if lines else "已执行"
            status = first_line if ("执行状态" in first_line or "Error" in first_line or "FAILED" in first_line) else "已完成"
            self.last_test_status = f"`{str(cmd)[:60]}` -> {status[:80]}"

    def format_prompt_context(self, compact: bool = False) -> str:
        """格式化为注入 Prompt 的注记块"""
        sections = []
        if self.current_goal:
            goal_preview = self.current_goal[:40] if compact else self.current_goal[:120]
            sections.append(f"- **当前协同目标**: {goal_preview}")
        if self.inspected_files:
            file_limit = 3 if compact else 8
            files_desc = ", ".join([f"`{f}` ({info})" for f, info in list(self.inspected_files.items())[-file_limit:]])
            sections.append(f"- **已排查代码**: {files_desc}")
        if self.modified_files:
            mod_limit = 3 if compact else 8
            mod_desc = ", ".join([f"`{f}`" for f in self.modified_files[-mod_limit:]])
            sections.append(f"- **已修改文件**: {mod_desc}")
        if self.last_test_status:
            sections.append(f"- **最新验证状态**: {self.last_test_status}")

        if not sections:
            return ""
        return "【系统注记 - 工作区感知状态 (Working Memory - 锁定保留)】:\n" + "\n".join(sections)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_goal": self.current_goal,
            "inspected_files": self.inspected_files,
            "modified_files": self.modified_files,
            "last_test_status": self.last_test_status,
        }

    def load_dict(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return
        self.current_goal = str(data.get("current_goal", ""))
        self.inspected_files = dict(data.get("inspected_files", {}))
        self.modified_files = list(data.get("modified_files", []))
        self.last_test_status = data.get("last_test_status")

    def clear(self):
        self.current_goal = ""
        self.inspected_files.clear()
        self.modified_files.clear()
        self.last_test_status = None


class ContextManager:
    """
    统一上下文调度中枢：
    严格兑现 5 大工程规范：
    1. System Prompt 绝对不可变 (Immutable)；
    2. Prompt 缓存友好架构：Base System + Summary + Active History 作为长效稳定前缀，高频 WorkingMemory 放置在历史之后；
    3. 全局硬预算分账 (BudgetLedger) 与最终硬门禁（Hard Gatekeeper 多级熔断防护）；
    4. 摘要区间锚点追踪与防抖护栏；
    5. 实时落盘事务性恢复（完整恢复 summary_state 与 working_memory，隔离未完成轮次）。
    """
    def __init__(
        self,
        session_id: str = "default",
        budget_ledger: Optional[BudgetLedger] = None,
        token_counter: Optional[TokenCounter] = None,
        summarizer: Optional[ContextSummarizer] = None
    ):
        self.session_id = session_id
        self.budget = budget_ledger.copy() if budget_ledger else default_budget_ledger.copy()
        self.token_counter = token_counter or default_token_counter
        self.window = SlidingWindow(self.token_counter)
        self.summarizer = summarizer or ContextSummarizer()
        self.working_memory = WorkingMemory()

        self.completed_turns: List[TurnChunk] = []
        self.current_turn: Optional[TurnChunk] = None
        self.turn_count: int = 0

        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        self.history_file = HISTORY_DIR / f"{self.session_id}.jsonl"

    @property
    def max_budget_tokens(self) -> int:
        return self.budget.total_budget

    @property
    def history_budget(self) -> int:
        return self.budget.history_budget

    def _append_to_disk(self, record_type: str, payload: Dict[str, Any]):
        """写盘日志追加，带立即刷新与错误记录"""
        try:
            entry = {
                "timestamp": time.time(),
                "session_id": self.session_id,
                "turn_id": self.turn_count,
                "type": record_type,
                "data": payload
            }
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                f.flush()
        except Exception as e:
            logger.error(f"持久化日志写入失败 [{record_type}]: {e}")

    def start_new_turn(self, user_content: str):
        self.turn_count += 1
        self.current_turn = TurnChunk(turn_id=self.turn_count)
        user_msg = {"role": "user", "content": user_content}
        self.current_turn.add_message(user_msg)
        self._append_to_disk("user_message", user_msg)

        if not self.working_memory.current_goal:
            self.working_memory.update_goal(user_content[:120])

    def add_assistant_message(self, message: Any):
        if not self.current_turn:
            self.start_new_turn("")

        if isinstance(message, ChatCompletionMessage):
            msg_dict: Dict[str, Any] = {"role": "assistant", "content": message.content or ""}
            if message.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
        elif isinstance(message, dict):
            msg_dict = message
        else:
            msg_dict = {"role": "assistant", "content": str(message)}

        self.current_turn.add_message(msg_dict)
        self._append_to_disk("assistant_message", msg_dict)

    def add_tool_results(self, tool_results: List[Dict[str, Any]]):
        if not self.current_turn:
            return

        for item in tool_results:
            tool_msg = {
                "role": "tool",
                "tool_call_id": item.get("tool_call_id", ""),
                "content": str(item.get("content", ""))
            }
            self.current_turn.add_message(tool_msg)
            self._append_to_disk("tool_result", tool_msg)

    def finish_current_turn(self):
        if self.current_turn:
            # 闭合校验与防御性清洗
            self.current_turn.sanitize_unpaired_calls()
            self.completed_turns.append(self.current_turn)
            self._append_to_disk("turn_finished", {
                "turn_id": self.current_turn.turn_id,
                "working_memory": self.working_memory.to_dict(),
                "summary_state": self.summarizer.state.to_dict()
            })
            self.current_turn = None

    def rollback_last_turn(self) -> bool:
        if self.completed_turns:
            rolled = self.completed_turns.pop()
            self.turn_count = max(0, self.turn_count - 1)
            self._append_to_disk("rollback", {"turn_id": rolled.turn_id})
            return True
        return False

    def clear(self):
        self._append_to_disk("session_cleared", {"turn_count": self.turn_count})
        self.completed_turns.clear()
        self.current_turn = None
        self.working_memory.clear()
        self.summarizer.clear()
        self.turn_count = 0

    def restore_from_disk(self) -> bool:
        """
        从本地磁盘恢复会话状态：
        关键保障：
        1. 完整反序列化 summary_state 与 working_memory；
        2. 严格事务性过滤未完成轮次（无 turn_finished 标记的轮次不进入 completed_turns）；
        3. 准确维护已回滚轮次与最大 turn_id。
        """
        if not self.history_file.exists():
            return False

        try:
            loaded_turns: Dict[int, TurnChunk] = {}
            finished_turn_ids: Set[int] = set()
            last_wm_data = None
            last_summary_data = None

            with open(self.history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except Exception:
                        continue

                    rec_type = record.get("type")
                    turn_id = record.get("turn_id", 0)

                    if rec_type in ["user_message", "assistant_message", "tool_result"]:
                        if turn_id not in loaded_turns:
                            loaded_turns[turn_id] = TurnChunk(turn_id=turn_id)
                        loaded_turns[turn_id].add_message(record.get("data", {}))

                    elif rec_type == "turn_finished":
                        finished_turn_ids.add(turn_id)
                        data = record.get("data", {})
                        wm = data.get("working_memory")
                        if wm:
                            last_wm_data = wm
                        sm = data.get("summary_state")
                        if sm:
                            last_summary_data = sm

                    elif rec_type == "rollback":
                        rb_id = record.get("data", {}).get("turn_id")
                        if rb_id in loaded_turns:
                            del loaded_turns[rb_id]
                        if rb_id in finished_turn_ids:
                            finished_turn_ids.remove(rb_id)

                    elif rec_type == "session_cleared":
                        loaded_turns.clear()
                        finished_turn_ids.clear()
                        last_wm_data = None
                        last_summary_data = None

            # 仅保留拥有 turn_finished 标记的完整轮次（隔离未完成轮次）
            valid_turns = [
                loaded_turns[tid] for tid in sorted(finished_turn_ids)
                if tid in loaded_turns and loaded_turns[tid].messages
            ]

            self.completed_turns = valid_turns
            self.turn_count = max(finished_turn_ids, default=0)
            self.current_turn = None

            # 完整恢复 WorkingMemory 与 SummaryState
            if last_wm_data:
                self.working_memory.load_dict(last_wm_data)
            if last_summary_data:
                self.summarizer.state.load_dict(last_summary_data)

            return len(self.completed_turns) > 0
        except Exception as e:
            logger.error(f"从磁盘恢复上下文失败: {e}", exc_info=True)
            return False

    def build_context_messages(
        self,
        base_system_prompt: str,
        client: Optional[OpenAI] = None,
        model: Optional[str] = None,
        tools_tokens: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        msgs, _ = self.build_context_with_watermark(
            base_system_prompt,
            client=client,
            model=model,
            tools_tokens=tools_tokens
        )
        return msgs

    def build_context_with_watermark(
        self,
        base_system_prompt: str,
        client: Optional[OpenAI] = None,
        model: Optional[str] = None,
        tools_tokens: Optional[int] = None,
        force_summary: bool = False
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        核心装配方法：
        1. 动态感知实际系统开销与工具 Token，校准可用历史预算；
        2. 三段式水位判定 (GREEN / YELLOW / RED)；
        3. 滑动窗口切分（保证时间轴绝对连续无穿孔）；
        4. Prompt 缓存友好顺序装配：Base System -> Summary -> Active History -> WorkingMemory -> Current Turn；
        5. 全局硬门禁 (Hard Gatekeeper) 多级熔断防御性截断。
        """
        # 1. 动态校准历史预算
        sys_tokens = self.token_counter.count_message({"role": "system", "content": base_system_prompt})
        actual_tools_tokens = tools_tokens if tools_tokens is not None else self.budget.tools_reserve
        self.budget.recalculate_history_budget(
            actual_system_tokens=sys_tokens,
            actual_tools_tokens=actual_tools_tokens
        )

        current_turn_msgs = self.current_turn.messages if self.current_turn else []
        current_turn_tokens = self.token_counter.count_messages(current_turn_msgs)

        all_historical_tokens = sum(c.estimate_tokens(self.token_counter) for c in self.completed_turns)
        total_history_tokens = all_historical_tokens + current_turn_tokens

        # 水位评估
        raw_utilization = self.token_counter.get_utilization(total_history_tokens, self.budget.history_budget)

        zone = WatermarkZone.GREEN
        active_chunks: List[TurnChunk] = []
        evicted_chunks: List[TurnChunk] = []
        did_summarize = False

        # --- 策略 A: 绿区 (< 60%) 全量直通 ---
        if raw_utilization < 0.60:
            zone = WatermarkZone.GREEN
            active_chunks = list(self.completed_turns)
            evicted_chunks = []

        # --- 策略 B: 黄区 (60% ~ 75%) 正常滑动窗口淘汰 ---
        elif 0.60 <= raw_utilization < 0.75:
            zone = WatermarkZone.YELLOW
            avail_budget = max(self.budget.min_history_budget, self.budget.history_budget - current_turn_tokens)
            active_chunks, evicted_chunks = self.window.split_by_budget(
                self.completed_turns,
                avail_budget
            )

        # --- 策略 C: 红区 (>= 75%) 深度压缩与防抖控制 ---
        else:
            zone = WatermarkZone.RED
            # 压缩后目标历史预算回落到 50% 水位左右
            target_history_budget = max(
                self.budget.min_history_budget,
                int(self.budget.history_budget * 0.50) - current_turn_tokens
            )
            active_chunks, evicted_chunks = self.window.split_by_budget(
                self.completed_turns,
                target_history_budget
            )

            # 防抖判定与摘要触发
            if evicted_chunks and self.summarizer.should_summarize(
                evicted_chunks,
                self.turn_count,
                self.token_counter,
                force=force_summary
            ):
                self.summarizer.summarize(
                    evicted_chunks,
                    self.turn_count,
                    client=client,
                    model=model
                )
                did_summarize = True

        # 4. Prompt 缓存友好顺序装配：
        #    1) Base System Prompt (不可变长效静态前缀)
        #    2) 长期纪要摘要 (低频变更)
        #    3) 活跃历史轮次 (中频稳定前缀增长)
        #    4) 工作区感知状态 WorkingMemory (高频状态注记，紧贴当前轮次)
        #    5) 当前轮次用户与交互消息
        final_messages: List[Dict[str, Any]] = [
            {"role": "system", "content": base_system_prompt}
        ]

        if self.summarizer.state.has_summary():
            range_header = self.summarizer.state.get_range_header()
            summary_block = f"{range_header}:\n{self.summarizer.state.summary_text}"
            final_messages.append({"role": "system", "content": summary_block})

        # 追加活跃历史轮次（保持长前缀稳定）
        for chunk in active_chunks:
            final_messages.extend(chunk.messages)

        # 注入工作区感知状态（放置于活跃历史之后，避免工具变动破坏全历史缓存）
        wm_context = self.working_memory.format_prompt_context(compact=False)
        if wm_context:
            final_messages.append({"role": "system", "content": wm_context})

        # 追加当前轮次
        if current_turn_msgs:
            final_messages.extend(current_turn_msgs)

        # 5. 全局硬门禁（Hard Gatekeeper）多级熔断防御截断：
        #    确保最终消息占用的总 Token 绝对不会侵占 output_reserve，绝不超总预算！
        max_context_allowed = self.budget.total_budget - self.budget.output_reserve
        actual_tokens = self.token_counter.count_messages(final_messages)
        hard_gatekeeper_triggered = False

        if actual_tokens > max_context_allowed:
            hard_gatekeeper_triggered = True
            logger.warning(
                f"触发硬门禁截断: 实际 Tokens ({actual_tokens}) 超过允许上限 ({max_context_allowed})，执行多级熔断截断保护。"
            )

            # 级别 1: 压缩 WorkingMemory
            if wm_context:
                compact_wm = self.working_memory.format_prompt_context(compact=True)
                for i, m in enumerate(final_messages):
                    if m.get("role") == "system" and "Working Memory" in m.get("content", ""):
                        final_messages[i]["content"] = compact_wm
                        break
                actual_tokens = self.token_counter.count_messages(final_messages)

            # 级别 2: 若仍超限，从最早的活跃轮次逐块安全剥离
            while actual_tokens > max_context_allowed and active_chunks:
                dropped_chunk = active_chunks.pop(0)
                dropped_ids = {id(m) for m in dropped_chunk.messages}
                final_messages = [m for m in final_messages if id(m) not in dropped_ids]
                actual_tokens = self.token_counter.count_messages(final_messages)

            # 级别 3: 若剥离所有活跃历史后仍然超限，彻底移除 WorkingMemory 注记
            if actual_tokens > max_context_allowed:
                final_messages = [
                    m for m in final_messages
                    if not (m.get("role") == "system" and "Working Memory" in m.get("content", ""))
                ]
                actual_tokens = self.token_counter.count_messages(final_messages)

            # 级别 4: 极端情况下若仍超限，对当前轮消息进行末尾保护性裁剪
            if actual_tokens > max_context_allowed and len(final_messages) > 1:
                # 保留 base system (final_messages[0])，对最后一条超长消息截断
                last_msg = final_messages[-1]
                content = str(last_msg.get("content", ""))
                excess_tokens = actual_tokens - max_context_allowed
                # 预估需裁减字符数 (保守估计 1 token ≈ 1.5 chars)
                trim_chars = int(excess_tokens * 2.5) + 20
                if len(content) > trim_chars:
                    last_msg["content"] = content[:-trim_chars] + "...[内容已达硬预算上限截断]"
                actual_tokens = self.token_counter.count_messages(final_messages)

        metrics = {
            "zone": zone,
            "raw_utilization": raw_utilization,
            "actual_tokens": actual_tokens,
            "max_budget": self.budget.total_budget,
            "history_budget": self.budget.history_budget,
            "output_reserve": self.budget.output_reserve,
            "active_turns": len(active_chunks),
            "evicted_turns": len(evicted_chunks),
            "has_summary": self.summarizer.state.has_summary(),
            "did_summarize": did_summarize,
            "hard_gatekeeper_triggered": hard_gatekeeper_triggered,
            "summary_range": (self.summarizer.state.start_turn_id, self.summarizer.state.end_turn_id)
        }

        return final_messages, metrics
