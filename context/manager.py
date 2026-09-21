# -*- coding: utf-8 -*-
import os
import re
import json
import time
import copy
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
    具备结果真实性校验，杜绝执行失败产生假阳性记录。
    """
    def __init__(self):
        self.current_goal: str = ""
        self._is_manual_goal: bool = False
        self.inspected_files: Dict[str, str] = {}
        self.modified_files: List[str] = []
        self.last_test_status: Optional[str] = None
        self.last_search_context: Optional[str] = None

    def update_goal(self, goal: str, is_manual: bool = True):
        if goal and str(goal).strip():
            self.current_goal = str(goal).strip()
            self._is_manual_goal = is_manual

    def update_from_tool(self, tool_name: str, args: Dict[str, Any], result: str):
        """解析并记录工具对工作区状态的改变，支持内置、检索与通用工具，严格校验执行成功结果"""
        if not isinstance(args, dict):
            return

        res_str = str(result) if result else ""
        has_error = any(w in res_str for w in ["Error", "Exception", "失败", "FAILED", "Errno", "未找到", "找不到"])

        # 1. 读文件排查 (成功且无报错)
        if tool_name in ["read_file", "view_file"]:
            filepath = args.get("file_path") or args.get("path") or ""
            start = args.get("start_line", 1)
            max_lines = args.get("max_lines", 100)
            if filepath and not has_error:
                self.inspected_files[str(filepath)] = f"第 {start} 至 {int(start) + int(max_lines) - 1} 行"

        # 2. 修改文件感知 (apply_patch, write_file, edit_file) - 需校验补丁是否成功应用
        elif tool_name == "apply_patch":
            if not has_error and ("成功" in res_str or "Applied" in res_str or "OK" in res_str):
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
            if filepath and not has_error and str(filepath) not in self.modified_files:
                self.modified_files.append(str(filepath).strip())

        # 3. 检索工具感知 (grep_text, find_by_name, list_files)
        elif tool_name in ["grep_text", "find_by_name", "list_files", "search"]:
            query = args.get("query") or args.get("pattern") or args.get("name") or ""
            count = len(res_str.splitlines())
            self.last_search_context = f"`{tool_name}({query})` -> 匹配 {count} 项"

        # 4. 命令行与测试感知
        elif tool_name in ["run_shell", "execute_command", "bash"]:
            cmd = args.get("command") or args.get("cmd") or ""
            lines = [l.strip() for l in res_str.splitlines() if l.strip()]
            first_line = lines[0] if lines else "已执行"
            status = first_line if ("执行状态" in first_line or has_error) else "已完成"
            self.last_test_status = f"`{str(cmd)[:60]}` -> {status[:80]}"

    def format_prompt_context(self, compact: bool = False) -> str:
        sections = []
        if self.current_goal:
            goal_preview = self.current_goal[:50] if compact else self.current_goal[:120]
            sections.append(f"- **当前协同目标**: {goal_preview}")
        if self.inspected_files:
            file_limit = 3 if compact else 8
            files_desc = ", ".join([f"`{f}` ({info})" for f, info in list(self.inspected_files.items())[-file_limit:]])
            sections.append(f"- **已排查代码**: {files_desc}")
        if self.modified_files:
            mod_limit = 3 if compact else 8
            mod_desc = ", ".join([f"`{f}`" for f in self.modified_files[-mod_limit:]])
            sections.append(f"- **已修改文件**: {mod_desc}")
        if self.last_search_context:
            sections.append(f"- **最近检索**: {self.last_search_context}")
        if self.last_test_status:
            sections.append(f"- **最新验证状态**: {self.last_test_status}")

        if not sections:
            return ""
        return "【系统注记 - 工作区感知状态 (Working Memory)】:\n" + "\n".join(sections)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_goal": self.current_goal,
            "_is_manual_goal": self._is_manual_goal,
            "inspected_files": self.inspected_files,
            "modified_files": self.modified_files,
            "last_test_status": self.last_test_status,
            "last_search_context": self.last_search_context
        }

    def load_dict(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return
        self.current_goal = str(data.get("current_goal", ""))
        self._is_manual_goal = bool(data.get("_is_manual_goal", False))
        self.inspected_files = dict(data.get("inspected_files", {}))
        self.modified_files = list(data.get("modified_files", []))
        self.last_test_status = data.get("last_test_status")
        self.last_search_context = data.get("last_search_context")

    def clear(self):
        self.current_goal = ""
        self._is_manual_goal = False
        self.inspected_files.clear()
        self.modified_files.clear()
        self.last_test_status = None
        self.last_search_context = None


class ContextManager:
    """
    统一上下文调度中枢：
    严格兑现 6 大工程规范：
    1. System Prompt 绝对不可变，全部系统注记置于对话历史头部；
    2. 解决永久红区陷阱：水位基于“未压缩历史 + 摘要开销 + 当前轮”动态升降；
    3. 消除信息黑洞：防抖期淘汰轮次即时触发轻量规则补偿更新摘要；
    4. 全协议兼容性：严禁在历史交互中间插入 system 角色；
    5. 全局硬门禁严格扣减 Tools Token，并提供多级自适应熔断；
    6. 事务性落盘恢复与多会话隔离。
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

        # 动态更新协同目标（尊重显式设定的目标）
        if not self.working_memory.current_goal:
            self.working_memory.update_goal(user_content[:120], is_manual=False)
        elif not self.working_memory._is_manual_goal:
            clean_input = user_content.strip()
            if len(clean_input) > 5 and not any(clean_input == w for w in ["继续", "ok", "OK", "好的", "下一步", "run"]):
                self.working_memory.update_goal(clean_input[:120], is_manual=False)

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

                    if rec_type == "session_cleared":
                        loaded_turns.clear()
                        finished_turn_ids.clear()
                        last_wm_data = None
                        last_summary_data = None
                        continue

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

            valid_turns = [
                loaded_turns[tid] for tid in sorted(finished_turn_ids)
                if tid in loaded_turns and loaded_turns[tid].messages
            ]

            self.completed_turns = valid_turns
            self.turn_count = max(finished_turn_ids, default=0)
            self.current_turn = None

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
        1. 动态校准历史预算（扣除真实 tools 与系统开销）；
        2. 水位动态升降：基于未归档历史+摘要自身开销，摘要后自然回落绿区，杜绝永久红区；
        3. 即时规则补偿：消除防抖黑洞；
        4. 全协议兼容性：所有 system 消息置于头部，绝不在交互历史中插入 system；
        5. 全局硬门禁多级自适应熔断截断。
        """
        actual_tools_tokens = tools_tokens if tools_tokens is not None else self.budget.tools_reserve
        sys_tokens = self.token_counter.count_message({"role": "system", "content": base_system_prompt})
        self.budget.recalculate_history_budget(
            actual_system_tokens=sys_tokens,
            actual_tools_tokens=actual_tools_tokens
        )

        current_turn_msgs = self.current_turn.messages if self.current_turn else []
        current_turn_tokens = self.token_counter.count_messages(current_turn_msgs)

        # 关键修复 1（消除永久红区陷阱）：
        # 水位评估基准为尚未被摘要覆盖的未归档轮次 + 摘要开销 + 当前轮次
        covered_id = self.summarizer.state.covered_through_turn_id
        uncompressed_turns = [c for c in self.completed_turns if c.turn_id > covered_id]
        uncompressed_tokens = sum(c.estimate_tokens(self.token_counter) for c in uncompressed_turns)
        summary_tokens = self.token_counter.count_text(self.summarizer.state.summary_text) if self.summarizer.state.has_summary() else 0

        effective_history_tokens = uncompressed_tokens + current_turn_tokens + summary_tokens
        raw_utilization = self.token_counter.get_utilization(effective_history_tokens, self.budget.history_budget)

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
            avail_budget = max(self.budget.min_history_budget, self.budget.history_budget - current_turn_tokens - summary_tokens)
            active_chunks, evicted_chunks = self.window.split_by_budget(
                self.completed_turns,
                avail_budget
            )
            # 关键修复 2（消除信息黑洞）：黄区淘汰轮次即时触发规则补偿
            if evicted_chunks:
                uncompacted = [c for c in evicted_chunks if c.turn_id > self.summarizer.state.covered_through_turn_id]
                if uncompacted:
                    self.summarizer.summarize(evicted_chunks, self.turn_count, use_llm=False)
                    did_summarize = True

        # --- 策略 C: 红区 (>= 75%) 深度压缩与防抖控制 ---
        else:
            zone = WatermarkZone.RED
            target_history_budget = max(
                self.budget.min_history_budget,
                int(self.budget.history_budget * 0.50) - current_turn_tokens - summary_tokens
            )
            active_chunks, evicted_chunks = self.window.split_by_budget(
                self.completed_turns,
                target_history_budget
            )

            if evicted_chunks:
                uncompacted = [c for c in evicted_chunks if c.turn_id > self.summarizer.state.covered_through_turn_id]
                if uncompacted:
                    if self.summarizer.should_summarize(evicted_chunks, self.turn_count, self.token_counter, force=force_summary):
                        self.summarizer.summarize(
                            evicted_chunks,
                            self.turn_count,
                            client=client,
                            model=model,
                            use_llm=True
                        )
                        did_summarize = True
                    else:
                        # 关键修复 3（消除信息黑洞）：防抖期执行轻量规则补偿
                        self.summarizer.summarize(
                            evicted_chunks,
                            self.turn_count,
                            use_llm=False
                        )
                        did_summarize = True

        # 关键修复 4（系统消息头部统一，绝不在交互历史中间插入 system）：
        final_messages: List[Dict[str, Any]] = [
            {"role": "system", "content": base_system_prompt}
        ]

        if self.summarizer.state.has_summary():
            range_header = self.summarizer.state.get_range_header()
            summary_block = f"{range_header}:\n{self.summarizer.state.summary_text}"
            final_messages.append({"role": "system", "content": summary_block})

        wm_context = self.working_memory.format_prompt_context(compact=False)
        if wm_context:
            final_messages.append({"role": "system", "content": wm_context})

        # 追加活跃历史轮次（格式纯净，user / assistant / tool 交替）
        for chunk in active_chunks:
            final_messages.extend(chunk.messages)

        # 追加当前轮次消息
        if current_turn_msgs:
            final_messages.extend(current_turn_msgs)

        # 关键修复 5（硬门禁上限严格扣除 Tools Token，并提供多级熔断）：
        max_context_allowed = self.budget.total_budget - self.budget.output_reserve - actual_tools_tokens
        actual_tokens = self.token_counter.count_messages(final_messages)
        hard_gatekeeper_triggered = False

        if actual_tokens > max_context_allowed:
            hard_gatekeeper_triggered = True
            logger.warning(
                f"触发硬门禁截断: 实际 Tokens ({actual_tokens}) 超过允许上限 ({max_context_allowed})，执行降级截断保护。"
            )

            # 级别 1: 压缩 WorkingMemory
            compact_wm = self.working_memory.format_prompt_context(compact=True)
            for m in final_messages:
                if m.get("role") == "system" and "Working Memory" in str(m.get("content", "")):
                    m["content"] = compact_wm
                    break
            actual_tokens = self.token_counter.count_messages(final_messages)

            # 级别 2: 从最早的活跃轮次逐块剥离
            while actual_tokens > max_context_allowed and active_chunks:
                dropped_chunk = active_chunks.pop(0)
                dropped_ids = {id(m) for m in dropped_chunk.messages}
                final_messages = [m for m in final_messages if id(m) not in dropped_ids]
                actual_tokens = self.token_counter.count_messages(final_messages)

            # 级别 3: 彻底移除 WorkingMemory
            if actual_tokens > max_context_allowed:
                final_messages = [
                    m for m in final_messages
                    if not (m.get("role") == "system" and "Working Memory" in str(m.get("content", "")))
                ]
                actual_tokens = self.token_counter.count_messages(final_messages)

            # 级别 4: 自适应压缩超长摘要
            if actual_tokens > max_context_allowed:
                for m in final_messages:
                    if m.get("role") == "system" and "历史排查与修改纪要" in str(m.get("content", "")):
                        c = str(m.get("content", ""))
                        if len(c) > 60:
                            m["content"] = c[:60] + "...[纪要已紧凑截断]"
                        break
                actual_tokens = self.token_counter.count_messages(final_messages)

            # 级别 5: 极端情况下裁剪最后一条超长输入
            if actual_tokens > max_context_allowed and len(final_messages) > 1:
                last_msg = final_messages[-1]
                content = str(last_msg.get("content", ""))
                excess_tokens = actual_tokens - max_context_allowed
                trim_chars = int(excess_tokens * 2.5) + 20
                if len(content) > trim_chars:
                    last_msg["content"] = content[:-trim_chars] + "...[输入已截断]"
                else:
                    last_msg["content"] = content[:20] + "...[输入已截断]"
                actual_tokens = self.token_counter.count_messages(final_messages)

        metrics = {
            "zone": zone,
            "raw_utilization": raw_utilization,
            "actual_tokens": actual_tokens,
            "max_budget": self.budget.total_budget,
            "history_budget": self.budget.history_budget,
            "output_reserve": self.budget.output_reserve,
            "tools_tokens": actual_tools_tokens,
            "active_turns": len(active_chunks),
            "evicted_turns": len(evicted_chunks),
            "has_summary": self.summarizer.state.has_summary(),
            "did_summarize": did_summarize,
            "hard_gatekeeper_triggered": hard_gatekeeper_triggered,
            "summary_range": (self.summarizer.state.start_turn_id, self.summarizer.state.end_turn_id)
        }

        return final_messages, metrics
