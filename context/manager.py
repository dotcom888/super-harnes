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

from tools.framework.workspace import default_workspace
from context.snapshot import default_snapshot_manager, SnapshotManager

def __getattr__(name: str):
    """动态获取工作区根路径或历史目录，杜绝 import 时静态绑定"""
    if name == "WORKSPACE_ROOT":
        return default_workspace.root
    if name == "HISTORY_DIR":
        d = default_workspace.root / "history"
        d.mkdir(parents=True, exist_ok=True)
        return d
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

class WatermarkZone:
    GREEN = "GREEN"    # < 60%: 全量直通
    YELLOW = "YELLOW"  # 60% ~ 75%: 正常滑动窗口淘汰
    RED = "RED"        # >= 75%: 触发 Summary Compaction (带防抖与区间记录)


class WorkingMemory:
    """
    工作区感知状态：锁定保留，不随滑窗淘汰。
    追踪当前协同目标、关键排查文件、已修改文件、最近检索与最新测试状态。
    具备结果真实性校验，杜绝执行失败产生假阳性记录，同时避免将包含 Error 关键字的代码内容误判为失败。
    """
    def __init__(self):
        self.current_goal: str = ""
        self._is_manual_goal: bool = False
        self.inspected_files: Dict[str, str] = {}
        self._file_ranges: Dict[str, List[Tuple[int, int]]] = {}
        self.modified_files: List[str] = []
        self._modified_file_turns: Dict[str, int] = {}
        self.last_test_status: Optional[str] = None
        self.last_search_context: Optional[str] = None

    def update_goal(self, goal: str, is_manual: bool = True):
        if goal and str(goal).strip():
            self.current_goal = str(goal).strip()
            self._is_manual_goal = is_manual

    def _record_file_range(self, filepath: str, start: int, end: int):
        """记录并智能合并排查文件区间，支持连续/重叠区间合并与去重，内部维护精确数值元组"""
        if not filepath:
            return
        fp = str(filepath).strip()
        new_start = min(int(start), int(end))
        new_end = max(int(start), int(end))
        new_range = (new_start, new_end)

        ranges = list(self._file_ranges.get(fp, []))
        if not ranges and fp in self.inspected_files:
            matches = re.findall(r"第\s*(\d+)\s*至\s*(\d+)\s*行", self.inspected_files[fp])
            ranges = [(int(s), int(e)) for s, e in matches]

        ranges.append(new_range)
        ranges.sort(key=lambda x: x[0])

        merged: List[Tuple[int, int]] = []
        for r_start, r_end in ranges:
            if not merged:
                merged.append((r_start, r_end))
            else:
                last_start, last_end = merged[-1]
                if r_start <= last_end + 1:
                    merged[-1] = (last_start, max(last_end, r_end))
                else:
                    merged.append((r_start, r_end))

        self._file_ranges[fp] = merged

        if len(merged) <= 3:
            desc = "; ".join([f"第 {s[0]} 至 {s[1]} 行" for s in merged])
        else:
            desc = f"第 {merged[0][0]} 至 {merged[0][1]} 行; 第 {merged[1][0]} 至 {merged[1][1]} 行 ... 第 {merged[-1][0]} 至 {merged[-1][1]} 行 (共 {len(merged)} 个区间)"

        self.inspected_files[fp] = desc

    def update_from_tool(self, tool_name: str, args: Dict[str, Any], result: str, turn_id: Optional[int] = None):
        """解析并记录工具对工作区状态的改变，精准判定失败前缀，泛化支持 MCP 与检索工具"""
        if not isinstance(args, dict):
            return

        res_str = str(result) if result else ""
        tool_lower = tool_name.lower()

        # 1. 读文件与大纲排查 (read_file, view_file, mcp 文件读取, outline)
        # 精准判断读取工具的错误前缀，绝不将代码正文中出现的 Error/Exception 误判为读取失败！
        if any(w in tool_lower for w in ["read_file", "view_file", "cat_file", "read", "outline"]):
            filepath = args.get("file_path") or args.get("path") or args.get("filepath") or ""
            start = args.get("start_line", 1)
            max_lines = args.get("max_lines", 100)
            
            # 仅当结果明确为读取报错时判定失败
            is_read_failed = (
                res_str.startswith("读取文件失败")
                or res_str.startswith("读取失败")
                or res_str.startswith("查看大纲失败")
                or res_str.startswith("生成大纲失败")
                or res_str.startswith("【安全拦截】")
                or res_str.startswith("Error:")
                or (len(res_str) < 120 and any(w in res_str for w in ["文件不存在", "未找到文件", "Permission denied", "NoSuchFile"]))
            )
            if filepath and not is_read_failed:
                if "outline" in tool_lower:
                    fp = str(filepath).strip()
                    if fp not in self.inspected_files:
                        self.inspected_files[fp] = "已查看代码大纲结构"
                else:
                    end_line = int(start) + int(max_lines) - 1
                    self._record_file_range(str(filepath), int(start), end_line)

        # 2. 修改文件感知 (apply_patch, write_file, edit_file)
        elif any(w in tool_lower for w in ["patch", "write_file", "create_file", "edit_file", "modify_file"]):
            if "patch" in tool_lower:
                # patch 工具成功时有明确标识
                is_patch_success = (
                    "【补丁成功】" in res_str
                    or "【创建成功】" in res_str
                    or "【补丁应用成功】" in res_str
                    or "【新建文件成功】" in res_str
                    or "Applied patch" in res_str
                    or "successfully" in res_str.lower()
                )
                if is_patch_success:
                    patch_content = args.get("patch_content", "")
                    created = re.findall(r"\*\*\*\s*(?:Create|Add)\s*File:\s*([^\n]+)", patch_content)
                    updated = re.findall(r"\*\*\*\s*Update\s*File:\s*([^\n]+)", patch_content)
                    diff_files = re.findall(r"diff --git a/[^\s]+ b/([^\s]+)", patch_content)
                    for f in created + updated + diff_files:
                        f_clean = f.strip()
                        if f_clean:
                            if f_clean not in self.modified_files:
                                self.modified_files.append(f_clean)
                            if turn_id is not None:
                                self._modified_file_turns[f_clean] = int(turn_id)
            else:
                filepath = args.get("file_path") or args.get("path")
                is_write_failed = res_str.startswith("写入失败") or res_str.startswith("【安全拦截】") or res_str.startswith("Error:")
                if filepath and not is_write_failed:
                    clean_fp = str(filepath).strip()
                    if clean_fp not in self.modified_files:
                        self.modified_files.append(clean_fp)
                    if turn_id is not None:
                        self._modified_file_turns[clean_fp] = int(turn_id)

        # 3. 检索工具感知 (grep_text, find_by_name, list_files, search)
        elif any(w in tool_lower for w in ["grep", "find", "list_files", "search"]):
            query = args.get("query") or args.get("pattern") or args.get("name") or args.get("path") or ""
            count = len(res_str.splitlines())
            self.last_search_context = f"`{tool_name}({query})` -> 匹配 {count} 项"

        # 4. 命令行与测试感知
        elif any(w in tool_lower for w in ["run_shell", "execute_command", "bash", "cmd"]):
            cmd = args.get("command") or args.get("cmd") or ""
            lines = [l.strip() for l in res_str.splitlines() if l.strip()]
            first_line = lines[0] if lines else "已执行"
            has_cmd_err = any(w in res_str[:200] for w in ["FAILED", "Error", "Exception", "Traceback", "失败"])
            status = first_line if ("执行状态" in first_line or has_cmd_err) else "已完成"
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
            mod_limit = 5 if compact else 15
            total_count = len(self.modified_files)
            selected = self.modified_files[-mod_limit:]
            parts = []
            for f in selected:
                t_id = self._modified_file_turns.get(f)
                turn_tag = f" (轮次 #{t_id})" if t_id else ""
                parts.append(f"`{f}`{turn_tag}")
            mod_desc = ", ".join(parts)
            if total_count > mod_limit:
                omitted = total_count - mod_limit
                mod_desc = f"... [早期前序省略 {omitted} 个] " + mod_desc + f" (累计已改 {total_count} 个文件)"
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
            "inspected_files": dict(self.inspected_files),
            "_file_ranges": {fp: [list(r) for r in ranges] for fp, ranges in self._file_ranges.items()},
            "modified_files": list(self.modified_files),
            "_modified_file_turns": dict(self._modified_file_turns),
            "last_test_status": self.last_test_status,
            "last_search_context": self.last_search_context
        }

    def load_dict(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return
        self.current_goal = str(data.get("current_goal", ""))
        self._is_manual_goal = bool(data.get("_is_manual_goal", False))
        self.inspected_files = dict(data.get("inspected_files", {}))
        self._file_ranges = {}
        raw_ranges = data.get("_file_ranges")
        if isinstance(raw_ranges, dict):
            for fp, r_list in raw_ranges.items():
                if isinstance(r_list, list):
                    self._file_ranges[str(fp)] = [
                        (int(r[0]), int(r[1]))
                        for r in r_list
                        if isinstance(r, (list, tuple)) and len(r) >= 2
                    ]
        for fp, desc in self.inspected_files.items():
            if fp not in self._file_ranges and isinstance(desc, str):
                matches = re.findall(r"第\s*(\d+)\s*至\s*(\d+)\s*行", desc)
                if matches:
                    self._file_ranges[fp] = [(int(s), int(e)) for s, e in matches]
        self.modified_files = list(data.get("modified_files", []))
        self._modified_file_turns = {
            str(k): int(v)
            for k, v in data.get("_modified_file_turns", {}).items()
            if isinstance(v, (int, float, str)) and str(v).isdigit()
        }
        self.last_test_status = data.get("last_test_status")
        self.last_search_context = data.get("last_search_context")

    def clear(self):
        self.current_goal = ""
        self._is_manual_goal = False
        self.inspected_files.clear()
        self._file_ranges.clear()
        self.modified_files.clear()
        self._modified_file_turns.clear()
        self.last_test_status = None
        self.last_search_context = None


class ContextManager:
    """
    统一上下文调度中枢：
    严格兑现工程规范：
    1. System Prompt 保持不可变只读；
    2. 水位评估消除永久红区，绿区消除历史与摘要双重注入；
    3. 前缀缓存友好：头部稳定系统注记，当前轮用户上下文注入；
    4. 消除跨会话 Turn ID 交叉污染与异常轮次假完成；
    5. 支持原子化快照回滚（同步还原 WorkingMemory 与 SummaryState）。
    """
    def __init__(
        self,
        session_id: str = "default",
        budget_ledger: Optional[BudgetLedger] = None,
        token_counter: Optional[TokenCounter] = None,
        summarizer: Optional[ContextSummarizer] = None,
        base_dir: Optional[Path] = None
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
        self._state_snapshots: List[Dict[str, Any]] = []

        # 真实 API 用量追踪 (Ground-Truth API Usage Feedback)
        self.last_api_prompt_tokens: int = 0
        self.last_api_completion_tokens: int = 0
        self.total_api_prompt_tokens: int = 0
        self.total_api_completion_tokens: int = 0

        self.workspace = default_workspace
        self._base_dir = Path(base_dir).resolve() if base_dir else None
        self.snapshot_manager = default_snapshot_manager
        self.last_rolled_back_files = []

        # 确保动态历史归档目录就绪
        self.history_dir.mkdir(parents=True, exist_ok=True)

        # 跨会话隔离：探测磁盘上已有历史的最大 turn_id，避免新会话从 1 开始导致 ID 碰撞
        self._init_turn_counter_from_disk()

    @property
    def history_dir(self) -> Path:
        """动态解析历史归档目录，随时随工作区根路径切换而重定向"""
        if self._base_dir:
            d = self._base_dir
        else:
            d = self.workspace.root / "history"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def history_file(self) -> Path:
        """动态生成当前会话的持久化 JSONL 文件路径"""
        return self.history_dir / f"{self.session_id}.jsonl"

    def _init_turn_counter_from_disk(self):
        if not self.history_file.exists():
            return
        try:
            max_id = 0
            with open(self.history_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        if record.get("type") == "session_cleared":
                            max_id = 0
                            continue
                        tid = record.get("turn_id", 0)
                        if isinstance(tid, int) and tid > max_id:
                            max_id = tid
                    except Exception:
                        pass
            self.turn_count = max_id
        except Exception:
            pass

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

    def record_api_usage(self, prompt_tokens: int, completion_tokens: int):
        """记录模型权威真实 API 消耗，便于监控与动态校准"""
        self.last_api_prompt_tokens = int(prompt_tokens or 0)
        self.last_api_completion_tokens = int(completion_tokens or 0)
        self.total_api_prompt_tokens += self.last_api_prompt_tokens
        self.total_api_completion_tokens += self.last_api_completion_tokens

    @staticmethod
    def _extract_clean_goal(text: str) -> Optional[str]:
        """
        启发式修剪提问中的礼貌/口语过渡前缀，提取核心协同目标短语
        - 若属于纯口语确认/推进词（如'好的'、'继续'、'下一步'），返回 None 保留原目标
        - 若包含实际指令，剥离前缀'好的/请/帮我/然后/继续'等，返回精炼动作目标
        """
        if not text:
            return None
        cleaned = text.strip()
        stop_words = {
            "继续", "ok", "OK", "Ok", "好的", "好的呢", "好", "行", "可以", 
            "下一步", "run", "go", "yes", "对的", "没问题", "接着来", "继续吧", "下一个"
        }
        if cleaned.lower() in stop_words or cleaned in stop_words:
            return None

        # 正则修剪过渡前缀（好的/好/请/帮我/麻烦/然后/接下来/继续/现在/下面/开始/下一个）及相连标点
        pattern = r"^(?:\s*(?:好的(?:呢)?|好|行|可以|请(?:你)?|帮我|麻烦(?:你)?|然后|接下来|继续|现在|下面|开始|下一个)[，,、\s]*)+"
        trimmed = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

        if not trimmed or trimmed.lower() in stop_words or trimmed in stop_words:
            return None

        # 核心短语有效长度校验 (>= 2 字符且不仅是标点)
        pure_chars = re.sub(r"[^\w\u4e00-\u9fa5]", "", trimmed)
        if len(pure_chars) >= 2:
            return trimmed[:120]
        return None

    def start_new_turn(self, user_content: str):
        self.turn_count += 1
        self.current_turn = TurnChunk(turn_id=self.turn_count)
        if hasattr(self, "snapshot_manager") and self.snapshot_manager:
            self.snapshot_manager.set_active_turn(self.session_id, self.turn_count)
        user_msg = {"role": "user", "content": user_content}
        self.current_turn.add_message(user_msg)
        self._append_to_disk("user_message", user_msg)

        extracted_goal = self._extract_clean_goal(user_content)
        if extracted_goal:
            if not self.working_memory.current_goal or not self.working_memory._is_manual_goal:
                self.working_memory.update_goal(extracted_goal, is_manual=False)
        elif not self.working_memory.current_goal and user_content.strip():
            self.working_memory.update_goal(user_content.strip()[:120], is_manual=False)

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
            
            # 记录本轮完成时的状态快照（用于原子化回滚）
            snapshot = {
                "turn_id": self.current_turn.turn_id,
                "working_memory": self.working_memory.to_dict(),
                "summary_state": self.summarizer.state.to_dict()
            }
            self._state_snapshots.append(snapshot)
            self.completed_turns.append(self.current_turn)
            self._append_to_disk("turn_finished", {
                "turn_id": self.current_turn.turn_id,
                "working_memory": snapshot["working_memory"],
                "summary_state": snapshot["summary_state"]
            })
            self.current_turn = None
            self.auto_vacuum_if_needed()

    def abort_current_turn(self):
        """异常中断时安全丢弃当前悬挂轮次，杜绝半截脏数据打上完成标记存盘"""
        if self.current_turn:
            aborted_id = self.current_turn.turn_id
            self._append_to_disk("turn_aborted", {"turn_id": aborted_id})
            self.current_turn = None
            self.turn_count = max(0, self.turn_count - 1)

    def rollback_last_turn(self, restore_disk: bool = True) -> bool:
        """回滚最近一轮：同步恢复 completed_turns、WorkingMemory 与 SummaryState，并联动还原物理磁盘文件"""
        if self.completed_turns:
            rolled = self.completed_turns.pop()
            rolled_turn_id = rolled.turn_id
            if self._state_snapshots:
                self._state_snapshots.pop()
                if self._state_snapshots:
                    prev = self._state_snapshots[-1]
                    self.working_memory.load_dict(prev["working_memory"])
                    self.summarizer.state.load_dict(prev["summary_state"])
                else:
                    self.working_memory.clear()
                    self.summarizer.clear()

            self.turn_count = max(0, self.turn_count - 1)
            self._append_to_disk("rollback", {"turn_id": rolled_turn_id})

            self.last_rolled_back_files = []
            if restore_disk and hasattr(self, "snapshot_manager") and self.snapshot_manager:
                try:
                    self.last_rolled_back_files = self.snapshot_manager.rollback_turn(
                        turn_id=rolled_turn_id,
                        session_id=self.session_id
                    )
                except Exception as e:
                    logger.error(f"物理磁盘回滚异常: {e}")

            return True
        self.last_rolled_back_files = []
        return False

    def vacuum(self) -> bool:
        """
        历史落盘日志事务瘦身与垃圾回收 (Log Compaction / Vacuum)
        - 消除废弃的 rollback、turn_aborted 和已清空的脏数据
        - 仅保留当前有效完成轮次及最终快照
        - 采用临时文件写入 + os.replace 原子替换，确保崩溃安全
        """
        if not self.history_file.exists():
            return False

        tmp_file = self.history_file.with_suffix(".jsonl.tmp")
        try:
            entries = []
            if not self.completed_turns:
                entries.append({
                    "timestamp": time.time(),
                    "session_id": self.session_id,
                    "turn_id": 0,
                    "type": "session_cleared",
                    "data": {"turn_count": 0}
                })
            else:
                snapshot_map = {s["turn_id"]: s for s in self._state_snapshots}
                for chunk in self.completed_turns:
                    tid = chunk.turn_id
                    for msg in chunk.messages:
                        role = msg.get("role")
                        rec_type = "user_message" if role == "user" else ("tool_result" if role == "tool" else "assistant_message")
                        entries.append({
                            "timestamp": time.time(),
                            "session_id": self.session_id,
                            "turn_id": tid,
                            "type": rec_type,
                            "data": msg
                        })
                    snap = snapshot_map.get(tid, {
                        "working_memory": self.working_memory.to_dict() if tid == self.turn_count else {},
                        "summary_state": self.summarizer.state.to_dict() if tid == self.turn_count else {}
                    })
                    entries.append({
                        "timestamp": time.time(),
                        "session_id": self.session_id,
                        "turn_id": tid,
                        "type": "turn_finished",
                        "data": {
                            "turn_id": tid,
                            "working_memory": snap.get("working_memory", {}),
                            "summary_state": snap.get("summary_state", {})
                        }
                    })

            with open(tmp_file, "w", encoding="utf-8") as f:
                for entry in entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_file, self.history_file)
            logger.info(f"会话日志压缩成功 (Vacuum): {self.history_file.name} 保留 {len(entries)} 条紧凑记录。")
            return True
        except Exception as e:
            logger.error(f"日志压缩 (Vacuum) 失败: {e}", exc_info=True)
            if tmp_file.exists():
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
            return False

    def auto_vacuum_if_needed(self, threshold_lines: int = 50, dead_ratio: float = 0.5):
        """当日志文件达到一定规模且无效脏记录占比超过阈值时自动压缩"""
        if not self.history_file.exists():
            return
        try:
            line_count = 0
            with open(self.history_file, "r", encoding="utf-8") as f:
                for _ in f:
                    line_count += 1
            valid_est = len(self.completed_turns) * 4
            if line_count >= threshold_lines and (line_count - valid_est) / line_count >= dead_ratio:
                self.vacuum()
        except Exception:
            pass

    def clear(self):
        self._append_to_disk("session_cleared", {"turn_count": self.turn_count})
        self.completed_turns.clear()
        self._state_snapshots.clear()
        self.current_turn = None
        self.working_memory.clear()
        self.summarizer.clear()
        self.turn_count = 0
        self.last_api_prompt_tokens = 0
        self.last_api_completion_tokens = 0
        self.total_api_prompt_tokens = 0
        self.total_api_completion_tokens = 0
        if hasattr(self, "snapshot_manager") and self.snapshot_manager:
            self.snapshot_manager.clear_session_snapshots(self.session_id)
        self.vacuum()

    def restore_from_disk(self) -> bool:
        if not self.history_file.exists():
            return False

        try:
            loaded_turns: Dict[int, TurnChunk] = {}
            finished_turn_ids: Set[int] = set()
            wm_history: Dict[int, Any] = {}
            summary_history: Dict[int, Any] = {}

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
                        self._state_snapshots.clear()
                        wm_history.clear()
                        summary_history.clear()
                        continue

                    if rec_type in ["user_message", "assistant_message", "tool_result"]:
                        if turn_id not in loaded_turns:
                            loaded_turns[turn_id] = TurnChunk(turn_id=turn_id)
                        loaded_turns[turn_id].add_message(record.get("data", {}))

                    elif rec_type == "turn_finished":
                        finished_turn_ids.add(turn_id)
                        data = record.get("data", {})
                        if "working_memory" in data and data["working_memory"]:
                            wm_history[turn_id] = data["working_memory"]
                        if "summary_state" in data and data["summary_state"]:
                            summary_history[turn_id] = data["summary_state"]

                    elif rec_type == "turn_aborted":
                        ab_id = record.get("data", {}).get("turn_id", turn_id)
                        if ab_id in loaded_turns:
                            del loaded_turns[ab_id]
                        if ab_id in finished_turn_ids:
                            finished_turn_ids.remove(ab_id)
                        if ab_id in wm_history:
                            del wm_history[ab_id]
                        if ab_id in summary_history:
                            del summary_history[ab_id]

                    elif rec_type == "rollback":
                        rb_id = record.get("data", {}).get("turn_id")
                        if rb_id in loaded_turns:
                            del loaded_turns[rb_id]
                        if rb_id in finished_turn_ids:
                            finished_turn_ids.remove(rb_id)
                        if rb_id in wm_history:
                            del wm_history[rb_id]
                        if rb_id in summary_history:
                            del summary_history[rb_id]

            valid_tids = sorted(finished_turn_ids)
            valid_turns = [
                loaded_turns[tid] for tid in valid_tids
                if tid in loaded_turns and loaded_turns[tid].messages
            ]

            self.completed_turns = valid_turns
            self.turn_count = max(valid_tids, default=0)
            self.current_turn = None

            # 同步重建历史状态快照栈，确保还原后执行 /undo 能够精准回滚工作记忆
            self._state_snapshots = [
                {
                    "turn_id": tid,
                    "working_memory": copy.deepcopy(wm_history.get(tid, {})),
                    "summary_state": copy.deepcopy(summary_history.get(tid, {}))
                }
                for tid in valid_tids
            ]

            last_tid = valid_tids[-1] if valid_tids else None
            if last_tid and last_tid in wm_history:
                self.working_memory.load_dict(wm_history[last_tid])
            else:
                self.working_memory.clear()

            if last_tid and last_tid in summary_history:
                self.summarizer.state.load_dict(summary_history[last_tid])
            else:
                self.summarizer.clear()

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
        1. 动态校准历史预算；
        2. 水位动态升降，彻底消除永久红区；
        3. 绿区消除双重注入：已有摘要时，活跃历史只装载未被摘要的轮次；
        4. 全协议与前缀缓存双重保障：头部集中 system 注记，交互历史保持纯净；
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

        # 统一候选轮次：若已有摘要，活跃轮次候选集仅从尚未被摘要吸收的轮次中选取，彻底杜绝绿/黄/红区双重注入
        candidate_turns = uncompressed_turns if self.summarizer.state.has_summary() else self.completed_turns

        # --- 策略 A: 绿区 (< 60%) ---
        if raw_utilization < 0.60:
            zone = WatermarkZone.GREEN
            active_chunks = list(candidate_turns)
            evicted_chunks = []

        # --- 策略 B: 黄区 (60% ~ 75%) 正常滑动窗口淘汰 ---
        elif 0.60 <= raw_utilization < 0.75:
            zone = WatermarkZone.YELLOW
            avail_budget = max(self.budget.min_history_budget, self.budget.history_budget - current_turn_tokens - summary_tokens)
            active_chunks, evicted_chunks = self.window.split_by_budget(
                candidate_turns,
                avail_budget
            )
            # 消除信息黑洞：黄区淘汰轮次即时触发规则补偿
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
                candidate_turns,
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
                        self.summarizer.summarize(
                            evicted_chunks,
                            self.turn_count,
                            use_llm=False
                        )
                        did_summarize = True

        # 头部系统注记组装（协议安全：全部 system 位于最头部，绝不在历史中间插入）
        final_messages: List[Dict[str, Any]] = [
            {"role": "system", "content": base_system_prompt}
        ]

        if self.summarizer.state.has_summary():
            range_header = self.summarizer.state.get_range_header()
            summary_block = f"{range_header}:\n{self.summarizer.state.summary_text}"
            final_messages.append({"role": "system", "content": summary_block})

        # 追加活跃历史轮次（无缝衔接：user / assistant / tool，历史前缀稳态命中 Prompt Cache）
        for chunk in active_chunks:
            final_messages.extend(chunk.messages)

        # 动态尾部：当前轮次消息
        # 消除 Prompt Cache 破坏：将高频动态变化的 WorkingMemory 注入到当前轮次首条 user 消息头部
        # 既避免了放在头部导致后续数千历史 Token 缓存失效，又避免了在历史中间插入独立 system 角色引发的 API 400
        wm_context = self.working_memory.format_prompt_context(compact=False)
        if current_turn_msgs:
            first_user_msg = current_turn_msgs[0]
            if wm_context and first_user_msg.get("role") == "user":
                annotated_user_content = f"{wm_context}\n\n[用户当前提问]: {first_user_msg.get('content', '')}"
                final_messages.append({"role": "user", "content": annotated_user_content})
                final_messages.extend(current_turn_msgs[1:])
            else:
                final_messages.extend(current_turn_msgs)
        elif wm_context:
            # 兼容无当前轮次（纯测试构造场景）
            final_messages.append({"role": "system", "content": wm_context})

        # 全局硬门禁（Hard Gatekeeper）多级自适应熔断：
        max_context_allowed = self.budget.total_budget - self.budget.output_reserve - actual_tools_tokens
        actual_tokens = self.token_counter.count_messages(final_messages)
        hard_gatekeeper_triggered = False

        if actual_tokens > max_context_allowed:
            hard_gatekeeper_triggered = True
            logger.warning(
                f"触发硬门禁截断: 实际 Tokens ({actual_tokens}) 超过允许上限 ({max_context_allowed})，执行降级截断保护。"
            )
            # 级别 1: 压缩 WorkingMemory（兼顾当前轮 user 注入与测试 system 注入）
            compact_wm = self.working_memory.format_prompt_context(compact=True)
            for m in final_messages:
                if m.get("role") == "user" and "Working Memory" in str(m.get("content", "")):
                    parts = str(m.get("content", "")).split("[用户当前提问]:", 1)
                    user_suffix = parts[1] if len(parts) > 1 else str(m.get("content", ""))
                    m["content"] = f"{compact_wm}\n\n[用户当前提问]:{user_suffix}"
                    break
                elif m.get("role") == "system" and "Working Memory" in str(m.get("content", "")):
                    m["content"] = compact_wm
                    break
            actual_tokens = self.token_counter.count_messages(final_messages)

            # 级别 2: 逐轮淘汰活跃轮次（先进先出）
            while actual_tokens > max_context_allowed and active_chunks:
                dropped_chunk = active_chunks.pop(0)
                dropped_ids = {id(m) for m in dropped_chunk.messages}
                final_messages = [m for m in final_messages if id(m) not in dropped_ids]
                actual_tokens = self.token_counter.count_messages(final_messages)

            # 级别 3: 彻底移除 WorkingMemory（剥离 user 消息前缀或清除 system 消息）
            if actual_tokens > max_context_allowed:
                for m in final_messages:
                    if m.get("role") == "user" and "Working Memory" in str(m.get("content", "")):
                        parts = str(m.get("content", "")).split("[用户当前提问]:", 1)
                        if len(parts) > 1:
                            m["content"] = parts[1].strip()
                        break
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
            "summary_range": (self.summarizer.state.start_turn_id, self.summarizer.state.end_turn_id),
            "last_api_prompt_tokens": self.last_api_prompt_tokens,
            "last_api_completion_tokens": self.last_api_completion_tokens,
            "total_api_tokens": self.total_api_prompt_tokens + self.total_api_completion_tokens
        }

        return final_messages, metrics
