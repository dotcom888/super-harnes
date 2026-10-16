# -*- coding: utf-8 -*-
"""
context/project_state.py: 项目级共享工作区感知与多会话状态总线 (Project State Bus)
管理跨会话共享的代码修改拓扑、排查行号区间、全局测试状态及与会话私有工作记忆的看板融合。
"""
import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from tools.framework.workspace import atomic_write_text

logger = logging.getLogger(__name__)

class ProjectState:
    """
    项目级全局工作区状态 (Project-wide Shared State):
    跨会话共享：
    1. 全局修改文件索引表 (global_modified_files): 记录文件由哪个 session 在哪个 turn 修改
    2. 全局代码排查区间 (global_inspected_files): 汇聚所有会话排查过的行号区间
    3. 全局最新测试/验证状态 (last_test_status)
    4. 全局最近检索 (last_search_context)
    """
    def __init__(self, project_dir: Optional[Path] = None, project_name: str = "default_project"):
        self.project_dir = Path(project_dir).resolve() if project_dir else None
        self.project_name = project_name
        self.global_modified_files: Dict[str, Dict[str, Any]] = {}
        self.global_inspected_files: Dict[str, str] = {}
        self._file_ranges: Dict[str, List[Tuple[int, int]]] = {}
        self.last_test_status: Optional[str] = None
        self.last_search_context: Optional[str] = None

        if self.project_dir and self.state_file.exists():
            self.load_from_disk()

    @property
    def state_file(self) -> Optional[Path]:
        if self.project_dir:
            return self.project_dir / "project_state.json"
        return None

    def record_file_modification(self, filepath: str, session_id: str, turn_id: Optional[int] = None):
        """记录跨会话文件修改溯源"""
        if not filepath:
            return
        clean_fp = str(filepath).strip()
        self.global_modified_files[clean_fp] = {
            "session_id": str(session_id),
            "turn_id": int(turn_id) if turn_id is not None else 1
        }
        self.save_to_disk()

    def record_file_range(self, filepath: str, start: int, end: int):
        """合并全局代码排查区间"""
        if not filepath:
            return
        fp = str(filepath).strip()
        new_start = min(int(start), int(end))
        new_end = max(int(start), int(end))
        new_range = (new_start, new_end)

        ranges = list(self._file_ranges.get(fp, []))
        if not ranges and fp in self.global_inspected_files:
            matches = re.findall(r"第\s*(\d+)\s*至\s*(\d+)\s*行", self.global_inspected_files[fp])
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
            desc = f"第 {merged[0][0]} 至 {merged[0][1]} 行 ... 第 {merged[-1][0]} 至 {merged[-1][1]} 行 (共 {len(merged)} 个区间)"

        self.global_inspected_files[fp] = desc
        self.save_to_disk()

    def record_tool_effect(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: str,
        session_id: str,
        turn_id: Optional[int] = None
    ):
        """解析工具对项目全局状态的改变并同步"""
        if not isinstance(args, dict):
            return

        res_str = str(result) if result else ""
        tool_lower = tool_name.lower()

        # 1. 读文件与大纲
        if any(w in tool_lower for w in ["read_file", "view_file", "cat_file", "read", "outline"]):
            filepath = args.get("file_path") or args.get("path") or args.get("filepath") or ""
            start = args.get("start_line", 1)
            max_lines = args.get("max_lines", 100)
            is_failed = (
                res_str.startswith("读取文件失败")
                or res_str.startswith("读取失败")
                or res_str.startswith("查看大纲失败")
                or res_str.startswith("【安全拦截】")
                or res_str.startswith("Error:")
            )
            if filepath and not is_failed:
                if "outline" in tool_lower:
                    fp = str(filepath).strip()
                    if fp not in self.global_inspected_files:
                        self.global_inspected_files[fp] = "已查看代码大纲结构"
                        self.save_to_disk()
                else:
                    end_line = int(start) + int(max_lines) - 1
                    self.record_file_range(str(filepath), int(start), end_line)

        # 2. 修改文件
        elif any(w in tool_lower for w in ["patch", "write_file", "create_file", "edit_file", "modify_file"]):
            if "patch" in tool_lower:
                is_patch_success = any(
                    kw in res_str for kw in [
                        "【补丁成功】", "【创建成功】", "【补丁应用成功】", "【新建文件成功】", "Applied patch", "successfully"
                    ]
                )
                if is_patch_success:
                    patch_content = args.get("patch_content", "")
                    created = re.findall(r"\*\*\*\s*(?:Create|Add)\s*File:\s*([^\n]+)", patch_content)
                    updated = re.findall(r"\*\*\*\s*Update\s*File:\s*([^\n]+)", patch_content)
                    diff_files = re.findall(r"diff --git a/[^\s]+ b/([^\s]+)", patch_content)
                    for f in created + updated + diff_files:
                        f_clean = f.strip()
                        if f_clean:
                            self.record_file_modification(f_clean, session_id, turn_id)
            else:
                filepath = args.get("file_path") or args.get("path")
                is_failed = res_str.startswith("写入失败") or res_str.startswith("【安全拦截】") or res_str.startswith("Error:")
                if filepath and not is_failed:
                    self.record_file_modification(str(filepath).strip(), session_id, turn_id)

        # 3. 检索工具
        elif any(w in tool_lower for w in ["grep", "find", "list_files", "search"]):
            query = args.get("query") or args.get("pattern") or args.get("name") or args.get("path") or ""
            count = len(res_str.splitlines())
            self.last_search_context = f"`{tool_name}({query})` -> 匹配 {count} 项"
            self.save_to_disk()

        # 4. 命令行与测试
        elif any(w in tool_lower for w in ["run_shell", "execute_command", "bash", "cmd"]):
            cmd = args.get("command") or args.get("cmd") or ""
            lines = [l.strip() for l in res_str.splitlines() if l.strip()]
            first_line = lines[0] if lines else "已执行"
            has_cmd_err = any(w in res_str[:200] for w in ["FAILED", "Error", "Exception", "Traceback", "失败"])
            status = first_line if ("执行状态" in first_line or has_cmd_err) else "已完成"
            self.last_test_status = f"`{str(cmd)[:60]}` -> {status[:80]}"
            self.save_to_disk()

    def rollback_session_turn(self, session_id: str, turn_id: int):
        """当指定会话回滚某轮时，同步剔除该会话在该轮登记的修改"""
        sid = str(session_id)
        tid = int(turn_id)
        to_del = []
        for fp, meta in self.global_modified_files.items():
            if meta.get("session_id") == sid and meta.get("turn_id") == tid:
                to_del.append(fp)
        for fp in to_del:
            del self.global_modified_files[fp]
        if to_del:
            self.save_to_disk()

    def clear_session(self, session_id: str):
        """清理指定会话的全局归属记录"""
        sid = str(session_id)
        to_del = [fp for fp, meta in self.global_modified_files.items() if meta.get("session_id") == sid]
        for fp in to_del:
            del self.global_modified_files[fp]
        if to_del:
            self.save_to_disk()

    def get_fusion_view(self, local_wm: Any, current_session_id: str, compact: bool = False) -> str:
        """
        生成【合二为一看板】 (Fusion Working Memory View):
        1. 包含本会话私有的协同目标
        2. 区分【本会话已改代码】与【项目其他会话改动】，0 冗余，0 冲突
        3. 聚合全局与本地排查过的行号区间
        4. 暴露最新验证状态与检索概况
        """
        sections = []

        # 1. 本会话协同目标（私有）
        if getattr(local_wm, "current_goal", ""):
            goal_text = local_wm.current_goal
            goal_preview = goal_text[:50] if compact else goal_text[:120]
            sections.append(f"- **当前会话协同目标**: {goal_preview}")

        # 2. 已改文件融合（本会话优先，其他会话补充溯源）
        local_mods = list(getattr(local_wm, "modified_files", []))
        local_turns = getattr(local_wm, "_modified_file_turns", {})

        # 本会话修改部分
        if local_mods:
            mod_limit = 5 if compact else 10
            selected_local = local_mods[-mod_limit:]
            local_parts = []
            for f in selected_local:
                t_id = local_turns.get(f)
                turn_tag = f" (轮次 #{t_id})" if t_id else ""
                local_parts.append(f"`{f}`{turn_tag}")
            local_desc = ", ".join(local_parts)
            if len(local_mods) > mod_limit:
                omitted = len(local_mods) - mod_limit
                local_desc = f"... [早期省略 {omitted} 个] " + local_desc
            sections.append(f"- **本会话已改代码**: {local_desc}")

        # 项目其他会话修改部分（不包含本会话已改过的文件，绝对去重）
        other_parts = []
        for fp, meta in self.global_modified_files.items():
            if fp not in local_mods and meta.get("session_id") != current_session_id:
                s_id = meta.get("session_id", "other")
                t_id = meta.get("turn_id", 1)
                other_parts.append(f"`{fp}` (由会话 #{s_id} 在轮次 #{t_id} 修改)")

        if other_parts:
            other_limit = 3 if compact else 8
            selected_other = other_parts[-other_limit:]
            other_desc = ", ".join(selected_other)
            if len(other_parts) > other_limit:
                other_desc = f"... [其他会话省略 {len(other_parts)-other_limit} 个] " + other_desc
            sections.append(f"- **项目其他会话协同改动**: {other_desc}")

        # 3. 排查代码区间融合（全局合并）
        merged_inspected: Dict[str, str] = dict(self.global_inspected_files)
        for fp, desc in getattr(local_wm, "inspected_files", {}).items():
            if fp not in merged_inspected:
                merged_inspected[fp] = desc

        if merged_inspected:
            file_limit = 3 if compact else 8
            files_desc = ", ".join([f"`{f}` ({info})" for f, info in list(merged_inspected.items())[-file_limit:]])
            sections.append(f"- **项目已排查代码**: {files_desc}")

        # 4. 最新检索与验证状态
        search_ctx = getattr(local_wm, "last_search_context", None) or self.last_search_context
        if search_ctx:
            sections.append(f"- **最近检索**: {search_ctx}")

        test_st = getattr(local_wm, "last_test_status", None) or self.last_test_status
        if test_st:
            sections.append(f"- **最新验证状态**: {test_st}")

        if not sections:
            return ""

        return "【系统注记 - 项目与工作区感知状态 (Working Memory)】:\n" + "\n".join(sections)

    def save_to_disk(self):
        """原子落盘 project_state.json"""
        if not self.project_dir:
            return
        self.project_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "project_name": self.project_name,
            "global_modified_files": self.global_modified_files,
            "global_inspected_files": self.global_inspected_files,
            "_file_ranges": {
                k: [list(r) for r in v] for k, v in self._file_ranges.items()
            },
            "last_test_status": self.last_test_status,
            "last_search_context": self.last_search_context
        }
        try:
            atomic_write_text(self.state_file, json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.warning(f"保存 project_state.json 失败: {e}")

    def load_from_disk(self):
        """反序列化 project_state.json"""
        if not self.state_file or not self.state_file.exists():
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.global_modified_files = dict(data.get("global_modified_files", {}))
            self.global_inspected_files = dict(data.get("global_inspected_files", {}))
            raw_ranges = data.get("_file_ranges", {})
            self._file_ranges = {}
            for k, v in raw_ranges.items():
                if isinstance(v, list):
                    self._file_ranges[k] = [(int(r[0]), int(r[1])) for r in v if isinstance(r, (list, tuple)) and len(r) >= 2]
            self.last_test_status = data.get("last_test_status")
            self.last_search_context = data.get("last_search_context")
        except Exception as e:
            logger.warning(f"读取 project_state.json 失败: {e}")
