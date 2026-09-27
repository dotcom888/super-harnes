# -*- coding: utf-8 -*-
"""
core/session.py: 项目级多会话（对话框）生命周期管理与隔离中枢
支持项目物理分箱、多会话并行、会话切换、自动反序列化唤醒、会话增删重命名与上下文严格隔离。
"""
import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from context.manager import ContextManager
from context.project_state import ProjectState
from config.settings import HISTORY_DIR
from tools.framework.workspace import default_workspace

logger = logging.getLogger(__name__)

class SessionManager:
    """
    项目级会话注册与隔离中心 (Session Manager):
    管理当前项目工作区下的所有会话 (Sessions)，持有该工程的 ProjectState 状态总线。
    各会话拥有私有的短期滑窗、任务目标与专属摘要，同时共享项目级已改文件与排查状态。
    """
    def __init__(
        self,
        default_session_id: str = "default",
        base_dir: Optional[Path] = None,
        history_dir: Optional[Path] = None,
        workspace: Optional[Any] = None,
        project_name: Optional[str] = None
    ):
        ws = workspace or default_workspace
        self.project_name = project_name or ws.root.name

        if history_dir:
            self.history_dir = Path(history_dir).resolve()
        elif base_dir:
            b_path = Path(base_dir).resolve()
            if b_path.name == self.project_name:
                self.history_dir = b_path
            elif b_path.name == "history":
                self.history_dir = b_path / self.project_name
            elif (b_path / "history").exists():
                self.history_dir = b_path / "history" / self.project_name
            else:
                self.history_dir = b_path / self.project_name
        else:
            # 默认建立项目独立子目录: history/<project_name>/
            self.history_dir = (HISTORY_DIR / self.project_name).resolve()

        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.base_dir = self.history_dir
        self.active_session_id = default_session_id
        self._sessions: Dict[str, ContextManager] = {}

        # 实例化项目全局共享状态总线 (Project State Bus)
        self.project_state = ProjectState(project_dir=self.history_dir, project_name=self.project_name)

        # 历史迁移感知：若顶层 history/ 下存在遗留的 default.jsonl，自动拷贝至项目子目录
        legacy_default = HISTORY_DIR / "default.jsonl"
        target_default = self.history_dir / "default.jsonl"
        if legacy_default.exists() and not target_default.exists() and self.history_dir != HISTORY_DIR:
            try:
                import shutil
                shutil.copy2(legacy_default, target_default)
            except Exception:
                pass

        # 初始化激活默认会话（若磁盘存在历史则自动加载）
        self.get_session(default_session_id, auto_restore=True)

        # 登记当前工作区工程至用户全局记忆索引
        try:
            from context.global_memory import default_global_memory
            default_global_memory.register_project(
                name=self.project_name,
                path=ws.root,
                description=f"本地工程 {self.project_name}"
            )
        except Exception:
            pass

    @property
    def active_session(self) -> ContextManager:
        """获取当前激活会话的 ContextManager"""
        return self.get_session(self.active_session_id, auto_restore=False)

    def get_session(self, session_id: str, auto_restore: bool = True) -> ContextManager:
        """
        获取或懒加载指定会话；若首次访问且磁盘存在历史则自动反序列化
        """
        sid = str(session_id).strip()
        if not sid:
            sid = "default"

        if sid not in self._sessions:
            mgr = ContextManager(
                session_id=sid,
                base_dir=self.base_dir,
                project_state=self.project_state,
                project_name=self.project_name
            )
            if auto_restore and mgr.history_file.exists():
                mgr.restore_from_disk()
            self._sessions[sid] = mgr
        return self._sessions[sid]

    def switch_session(self, session_id: str, auto_restore: bool = True) -> ContextManager:
        """
        切换当前激活会话
        """
        sid = str(session_id).strip()
        if not sid:
            raise ValueError("会话名称不能为空。")

        target_mgr = self.get_session(sid, auto_restore=auto_restore)
        self.active_session_id = sid
        try:
            from tools.framework.policies import default_policy
            default_policy.reset_session_approval()
        except Exception:
            pass
        return target_mgr

    def create_session(self, session_id: Optional[str] = None) -> ContextManager:
        """
        创建新会话并自动切换过去
        如果未指定名称，则自动生成 session_1, session_2...
        """
        if not session_id or not str(session_id).strip():
            existing = {s["session_id"] for s in self.list_sessions()}
            idx = 1
            while f"session_{idx}" in existing or f"session_{idx}" in self._sessions:
                idx += 1
            session_id = f"session_{idx}"

        sid = str(session_id).strip()
        sid = re.sub(r"[^\w\-]", "_", sid)

        mgr = ContextManager(
            session_id=sid,
            base_dir=self.base_dir,
            project_state=self.project_state,
            project_name=self.project_name
        )
        mgr.clear()
        self._sessions[sid] = mgr
        self.active_session_id = sid
        try:
            from tools.framework.policies import default_policy
            default_policy.reset_session_approval()
        except Exception:
            pass
        return mgr

    def delete_session(self, session_id: str) -> bool:
        """
        删除指定会话（销毁内存并清理磁盘文件）
        禁止删除当前唯一的活动会话（若删除当前会话，则自动切换至 default）
        """
        sid = str(session_id).strip()
        target_file = self.history_dir / f"{sid}.jsonl"
        tmp_file = self.history_dir / f"{sid}.jsonl.tmp"

        if sid in self._sessions:
            del self._sessions[sid]

        if target_file.exists():
            try:
                target_file.unlink()
            except Exception as e:
                logger.warning(f"删除会话日志文件失败: {e}")

        if tmp_file.exists():
            try:
                tmp_file.unlink()
            except Exception:
                pass

        if self.project_state:
            self.project_state.clear_session(sid)

        if self.active_session_id == sid:
            self.active_session_id = "default"
            self.get_session("default", auto_restore=True)

        return True

    def rename_session(self, old_id: str, new_id: str) -> bool:
        """
        重命名会话并物理移动磁盘 .jsonl 文件
        """
        old_sid = str(old_id).strip()
        new_sid = str(new_id).strip()
        new_sid = re.sub(r"[^\w\-]", "_", new_sid)

        if not new_sid or old_sid == new_sid:
            return False

        old_file = self.history_dir / f"{old_sid}.jsonl"
        new_file = self.history_dir / f"{new_sid}.jsonl"

        if old_sid not in self._sessions and not old_file.exists():
            return False

        old_mgr = self.get_session(old_sid, auto_restore=True)

        if old_file.exists():
            if new_file.exists():
                try:
                    new_file.unlink()
                except Exception:
                    pass
            try:
                os.replace(old_file, new_file)
            except Exception as e:
                logger.error(f"物理重命名日志文件失败: {e}")

        new_mgr = ContextManager(
            session_id=new_sid,
            base_dir=self.base_dir,
            project_state=self.project_state,
            project_name=self.project_name
        )
        if new_file.exists():
            new_mgr.restore_from_disk()
        else:
            new_mgr.completed_turns = old_mgr.completed_turns
            new_mgr.working_memory.load_dict(old_mgr.working_memory.to_dict())
            new_mgr.summarizer.state.load_dict(old_mgr.summarizer.state.to_dict())
            new_mgr.turn_count = old_mgr.turn_count

        if old_sid in self._sessions:
            del self._sessions[old_sid]
        self._sessions[new_sid] = new_mgr

        if self.active_session_id == old_sid:
            self.active_session_id = new_sid

        return True

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        汇总当前项目所有会话（内存 + 磁盘 history/<project>/*.jsonl）元数据列表
        """
        all_sids = set(self._sessions.keys())
        if self.history_dir.exists():
            for f in self.history_dir.glob("*.jsonl"):
                stem = f.stem
                if not stem.endswith(".tmp"):
                    all_sids.add(stem)

        all_sids.add("default")

        result = []
        for sid in sorted(all_sids):
            mgr = self.get_session(sid, auto_restore=True)
            f_path = self.history_dir / f"{sid}.jsonl"
            mtime = f_path.stat().st_mtime if f_path.exists() else 0

            wm = mgr.working_memory
            mod_count = len(wm.modified_files)
            preview_goal = wm.current_goal or "（未指定目标）"

            result.append({
                "session_id": sid,
                "project_name": self.project_name,
                "is_active": (sid == self.active_session_id),
                "turn_count": mgr.turn_count,
                "modified_files_count": mod_count,
                "current_goal": preview_goal,
                "mtime": mtime,
                "has_disk_file": f_path.exists()
            })

        result.sort(key=lambda x: (not x["is_active"], -x["mtime"]))
        return result

    def get_session_preview(self, session_id: str) -> str:
        """
        生成紧凑的会话上下文回显（包含项目全局协同感知与本会话状态、最近问答），供切换时展示
        """
        mgr = self.get_session(session_id, auto_restore=True)
        active_str = "【当前激活】" if session_id == self.active_session_id else "就绪"
        lines = [f"\n{'='*20} 项目 【{self.project_name}】 会话 【{session_id}】 上下文快照 {'='*20}"]
        lines.append(f"• 累计轮次: {mgr.turn_count} 轮 | 状态: {active_str}")
        wm = mgr.working_memory
        if wm.current_goal:
            lines.append(f"• 当前会话协同目标: {wm.current_goal}")
        if wm.modified_files:
            mod_str = ", ".join(wm.modified_files[:5]) + (" 等" if len(wm.modified_files) > 5 else "")
            lines.append(f"• 本会话已改代码 ({len(wm.modified_files)} 个): {mod_str}")

        # 项目全局协同改动感知
        other_files = [
            f"`{fp}` (会话 #{meta.get('session_id')} 轮次 #{meta.get('turn_id')})"
            for fp, meta in self.project_state.global_modified_files.items()
            if fp not in wm.modified_files and meta.get("session_id") != session_id
        ]
        if other_files:
            lines.append(f"• 项目其他会话协同改动 ({len(other_files)} 个): {', '.join(other_files[:3])}{' 等' if len(other_files) > 3 else ''}")

        if wm.inspected_files:
            lines.append(f"• 已排查代码: {', '.join(list(wm.inspected_files.keys())[:5])}")

        if mgr.completed_turns:
            lines.append("• 最近对话历史:")
            for turn in mgr.completed_turns[-2:]:
                user_msg = next((m.get("content", "") for m in turn.messages if m.get("role") == "user"), "")
                if "[用户当前提问]:" in user_msg:
                    user_msg = user_msg.split("[用户当前提问]:", 1)[1].strip()
                elif "【系统注记" in user_msg:
                    user_msg = user_msg.split("\n\n")[-1].strip()

                assist_msg = next((m.get("content", "") for m in reversed(turn.messages) if m.get("role") == "assistant" and m.get("content")), "")
                user_display = (user_msg[:60] + "...") if len(user_msg) > 60 else user_msg
                assist_display = (assist_msg[:60] + "...") if len(assist_msg) > 60 else assist_msg
                if not assist_display:
                    assist_display = "（执行工具排查与修改）"
                lines.append(f"  - [轮次 #{turn.turn_id}] 用户: {user_display}")
                lines.append(f"             助手: {assist_display}")
        else:
            lines.append("• 历史消息: （全新空白会话）")

        lines.append("="*64)
        return "\n".join(lines)
