# -*- coding: utf-8 -*-
import os
import re
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

from context.token_counter import TokenCounter, default_token_counter
from context.window import TurnChunk, SlidingWindow
from context.summarizer import ContextSummarizer
from context.budget import BudgetLedger, default_budget_ledger

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = WORKSPACE_ROOT / "history"

class WatermarkZone:
    GREEN = "GREEN"    # < 60%: 全量直通
    YELLOW = "YELLOW"  # 60% ~ 75%: 正常滑动窗口淘汰
    RED = "RED"        # >= 75%: 触发 Summary Compaction (带防抖与区间记录)


class WorkingMemory:
    """
    工作区感知状态：锁定保留，不随滑窗淘汰。
    """
    def __init__(self):
        self.current_goal: str = ""
        self.inspected_files: Dict[str, str] = {}
        self.modified_files: List[str] = []
        self.last_test_status: Optional[str] = None

    def update_goal(self, goal: str):
        if goal and goal.strip():
            self.current_goal = goal.strip()

    def update_from_tool(self, tool_name: str, args: Dict[str, Any], result: str):
        if tool_name == "read_file":
            filepath = args.get("file_path", "")
            start = args.get("start_line", 1)
            max_lines = args.get("max_lines", 100)
            if filepath:
                self.inspected_files[filepath] = f"第 {start} 至 {int(start) + int(max_lines) - 1} 行"

        elif tool_name == "apply_patch":
            patch_content = args.get("patch_content", "")
            created = re.findall(r"\*\*\*\s*Create File:\s*([^\n]+)", patch_content)
            updated = re.findall(r"\*\*\*\s*Update File:\s*([^\n]+)", patch_content)
            for f in created + updated:
                f_clean = f.strip()
                if f_clean not in self.modified_files:
                    self.modified_files.append(f_clean)

        elif tool_name == "run_shell":
            cmd = args.get("command", "")
            first_line = result.splitlines()[0] if result else ""
            status = first_line if "执行状态" in first_line else "已执行"
            self.last_test_status = f"`{cmd}` -> {status}"

    def format_prompt_context(self) -> str:
        sections = []
        if self.current_goal:
            sections.append(f"- **当前协同目标**: {self.current_goal}")
        if self.inspected_files:
            files_desc = ", ".join([f"`{f}` ({info})" for f, info in list(self.inspected_files.items())[-8:]])
            sections.append(f"- **已排查代码**: {files_desc}")
        if self.modified_files:
            mod_desc = ", ".join([f"`{f}`" for f in self.modified_files[-8:]])
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
        self.current_goal = data.get("current_goal", "")
        self.inspected_files = data.get("inspected_files", {})
        self.modified_files = data.get("modified_files", [])
        self.last_test_status = data.get("last_test_status")

    def clear(self):
        self.current_goal = ""
        self.inspected_files.clear()
        self.modified_files.clear()
        self.last_test_status = None


class ContextManager:
    """
    统一上下文调度中枢：
    严格兑现 4 大工程规范：
    1. System Prompt 绝对不可变 (Immutable)，动态内容作为独立系统注记装配，保持 Prompt Cache；
    2. 全局硬预算分账 (BudgetLedger)，历史滑窗严格运行在独立额度 (默认 15,000) 内；
    3. 摘要区间锚点追踪 (Range Tracking: #start ~ #end)；
    4. 防摘要抖动护栏 (Debounce Guard: 最小轮数、最小Token、冷却周期)。
    """
    def __init__(
        self,
        session_id: str = "default",
        budget_ledger: Optional[BudgetLedger] = None,
        token_counter: Optional[TokenCounter] = None,
        summarizer: Optional[ContextSummarizer] = None
    ):
        self.session_id = session_id
        self.budget = budget_ledger or default_budget_ledger
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
        except Exception:
            pass

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
        if not self.history_file.exists():
            return False

        try:
            loaded_turns: Dict[int, TurnChunk] = {}
            last_wm_data = None

            with open(self.history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    rec_type = record.get("type")
                    turn_id = record.get("turn_id", 0)

                    if rec_type in ["user_message", "assistant_message", "tool_result"]:
                        if turn_id not in loaded_turns:
                            loaded_turns[turn_id] = TurnChunk(turn_id=turn_id)
                        loaded_turns[turn_id].add_message(record.get("data", {}))

                    elif rec_type == "turn_finished":
                        wm = record.get("data", {}).get("working_memory")
                        if wm:
                            last_wm_data = wm

                    elif rec_type == "rollback":
                        rb_id = record.get("data", {}).get("turn_id")
                        if rb_id in loaded_turns:
                            del loaded_turns[rb_id]

                    elif rec_type == "session_cleared":
                        loaded_turns.clear()
                        last_wm_data = None

            sorted_turns = [loaded_turns[k] for k in sorted(loaded_turns.keys()) if loaded_turns[k].messages]
            self.completed_turns = sorted_turns
            self.turn_count = len(sorted_turns)
            self.current_turn = None
            if last_wm_data:
                self.working_memory.load_dict(last_wm_data)

            return len(self.completed_turns) > 0
        except Exception:
            return False

    def build_messages(
        self,
        base_system_prompt: str,
        client: Optional[OpenAI] = None,
        model: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        msgs, _ = self.build_context_with_watermark(base_system_prompt, client, model)
        return msgs

    def build_context_with_watermark(
        self,
        base_system_prompt: str,
        client: Optional[OpenAI] = None,
        model: Optional[str] = None,
        force_summary: bool = False
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        核心装配方法：
        1. base_system_prompt 保持不可变只读，严禁原地拼接污染；
        2. 历史滑动窗口严格在 self.history_budget (15,000 Tokens) 独立额度内运作；
        3. 水位判定基于历史额度；
        4. >=75% 触发带防抖判定与区间记录的 Summary 压缩。
        """
        # 1. 计算当前历史与进行中轮次的真实 Token
        current_turn_msgs = self.current_turn.messages if self.current_turn else []
        current_turn_tokens = self.token_counter.count_messages(current_turn_msgs)

        all_historical_tokens = sum(c.estimate_tokens(self.token_counter) for c in self.completed_turns)
        total_history_tokens = all_historical_tokens + current_turn_tokens

        # 水位基准：基于 History 专属预算 (例如 15,000) 评估
        raw_utilization = self.token_counter.get_utilization(total_history_tokens, self.history_budget)

        zone = WatermarkZone.GREEN
        active_chunks = []
        evicted_chunks = []
        did_summarize = False

        # --- 策略 A: 绿区 (< 60%) 全量直通 ---
        if raw_utilization < 0.60:
            zone = WatermarkZone.GREEN
            active_chunks = list(self.completed_turns)
            evicted_chunks = []

        # --- 策略 B: 黄区 (60% ~ 75%) 正常滑动窗口淘汰 ---
        elif 0.60 <= raw_utilization < 0.75:
            zone = WatermarkZone.YELLOW
            avail_budget = max(50, self.history_budget - current_turn_tokens)
            active_chunks, evicted_chunks = self.window.split_by_budget(
                self.completed_turns,
                avail_budget
            )

        # --- 策略 C: 红区 (>= 75%) 深度压缩与防抖控制 ---
        else:
            zone = WatermarkZone.RED
            # 压缩后目标历史预算回落到 50% 水位左右
            target_history_budget = max(50, int(self.history_budget * 0.50) - current_turn_tokens)
            active_chunks, evicted_chunks = self.window.split_by_budget(
                self.completed_turns,
                target_history_budget
            )

            # 防抖判定：检查是否满足最小新增轮数、最小Token与冷却周期
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

        # 4. 组装输出（原则 1：base_system_prompt 保持纯洁，动态内容作为独立系统注记注入）
        final_messages: List[Dict[str, Any]] = [
            {"role": "system", "content": base_system_prompt}
        ]

        # 注入长期记忆摘要块（带区间锚点）
        if self.summarizer.state.has_summary():
            range_header = self.summarizer.state.get_range_header()
            summary_block = f"{range_header}:\n{self.summarizer.state.summary_text}"
            final_messages.append({"role": "system", "content": summary_block})

        # 注入工作区感知状态块
        wm_context = self.working_memory.format_prompt_context()
        if wm_context:
            final_messages.append({"role": "system", "content": wm_context})

        # 追加活跃历史轮次
        for chunk in active_chunks:
            final_messages.extend(chunk.messages)

        # 追加当前正在执行的一轮
        if current_turn_msgs:
            final_messages.extend(current_turn_msgs)

        actual_tokens = self.token_counter.count_messages(final_messages)

        metrics = {
            "zone": zone,
            "raw_utilization": raw_utilization,
            "actual_tokens": actual_tokens,
            "max_budget": self.budget.total_budget,
            "history_budget": self.history_budget,
            "active_turns": len(active_chunks),
            "evicted_turns": len(evicted_chunks),
            "has_summary": self.summarizer.state.has_summary(),
            "did_summarize": did_summarize,
            "summary_range": (self.summarizer.state.start_turn_id, self.summarizer.state.end_turn_id)
        }

        return final_messages, metrics
