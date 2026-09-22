# -*- coding: utf-8 -*-
"""
context/snapshot.py: 物理磁盘快照与回滚管理器
1. 写前快照 (Shadow Snapshot)：在修改或写入文件前备份原始版本；
2. 多文件事务原子性 (Patch Transaction)：修改失败时自动回滚磁盘；
3. 真实 /undo 物理联动：在用户输入 /undo 回滚轮次时，精确还原被修改/新增的文件。
"""
import os
import shutil
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple, Any

from tools.framework.workspace import default_workspace

logger = logging.getLogger(__name__)

class FileSnapshotRecord:
    """单个文件快照条目记录"""
    def __init__(
        self,
        abs_path: Path,
        rel_path: str,
        action: str,  # "modify" 或 "create"
        backup_path: Optional[Path] = None
    ):
        self.abs_path = Path(abs_path).resolve()
        self.rel_path = rel_path
        self.action = action
        self.backup_path = Path(backup_path).resolve() if backup_path else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "abs_path": str(self.abs_path),
            "rel_path": self.rel_path,
            "action": self.action,
            "backup_path": str(self.backup_path) if self.backup_path else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileSnapshotRecord":
        return cls(
            abs_path=Path(data["abs_path"]),
            rel_path=data["rel_path"],
            action=data["action"],
            backup_path=Path(data["backup_path"]) if data.get("backup_path") else None
        )

class SnapshotManager:
    """
    负责本地终端物理磁盘文件快照与还原
    快照保存在：<workspace_root>/.super-harnes/snapshots/session_{session_id}/turn_{turn_id}/
    """
    def __init__(self, workspace=default_workspace):
        self.workspace = workspace
        self.active_session_id: str = "default"
        self.active_turn_id: int = 0
        # 内存记录：{ (turn_id, rel_path): FileSnapshotRecord }
        self._turn_records: Dict[Tuple[int, str], FileSnapshotRecord] = {}

    @property
    def base_snapshot_dir(self) -> Path:
        return self.workspace.root / ".super-harnes" / "snapshots"

    def get_turn_dir(self, session_id: str, turn_id: int) -> Path:
        return self.base_snapshot_dir / f"session_{session_id}" / f"turn_{turn_id}"

    def set_active_turn(self, session_id: str, turn_id: int):
        """同步设置当前活动的 session_id 和 turn_id"""
        self.active_session_id = session_id
        self.active_turn_id = turn_id

    def backup_before_mutation(self, file_path: Union[str, Path]) -> Optional[FileSnapshotRecord]:
        """
        在写入或修改文件前创建物理快照。
        若本轮已备份过该文件，则保留最开始的原始版本，绝不重复覆盖备份。
        """
        abs_path = self.workspace.resolve_path(file_path)
        try:
            rel_path = self.workspace.relative_path(abs_path)
        except Exception:
            rel_path = abs_path.name

        turn_id = self.active_turn_id
        key = (turn_id, rel_path)

        # 核心防线：本轮若已备份该文件，绝不可覆盖，保持轮次开始前的最原始状态
        if key in self._turn_records:
            return self._turn_records[key]

        turn_dir = self.get_turn_dir(self.active_session_id, turn_id)
        record: Optional[FileSnapshotRecord] = None

        if abs_path.exists() and abs_path.is_file():
            backup_file = turn_dir / "files" / rel_path
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(abs_path, backup_file)
                record = FileSnapshotRecord(
                    abs_path=abs_path,
                    rel_path=rel_path,
                    action="modify",
                    backup_path=backup_file
                )
            except Exception as e:
                logger.warning(f"备份文件失败 '{abs_path}': {e}")
                return None
        else:
            record = FileSnapshotRecord(
                abs_path=abs_path,
                rel_path=rel_path,
                action="create",
                backup_path=None
            )

        if record:
            self._turn_records[key] = record
            self._save_turn_manifest(self.active_session_id, turn_id)

        return record

    def _save_turn_manifest(self, session_id: str, turn_id: int):
        """将本轮快照索引持久化至磁盘 manifest.json"""
        turn_dir = self.get_turn_dir(session_id, turn_id)
        turn_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = turn_dir / "manifest.json"

        records_data = []
        for (t_id, _), rec in self._turn_records.items():
            if t_id == turn_id:
                records_data.append(rec.to_dict())

        try:
            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump({
                    "turn_id": turn_id,
                    "session_id": session_id,
                    "records": records_data
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存快照 manifest 失败: {e}")

    def _load_turn_manifest(self, session_id: str, turn_id: int) -> List[FileSnapshotRecord]:
        """从磁盘读取某轮的快照清单"""
        turn_dir = self.get_turn_dir(session_id, turn_id)
        manifest_file = turn_dir / "manifest.json"
        if not manifest_file.exists():
            return []
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [FileSnapshotRecord.from_dict(d) for d in data.get("records", [])]
        except Exception as e:
            logger.warning(f"读取快照 manifest 失败: {e}")
            return []

    def rollback_turn(self, turn_id: int, session_id: Optional[str] = None) -> List[str]:
        """
        物理磁盘回滚指定轮次的修改
        :return: 还原或清理的文件描述列表，例如 ['foo.py (已还原)', 'bar.py (已删除新建文件)']
        """
        sess_id = session_id or self.active_session_id
        records = [rec for (t_id, _), rec in self._turn_records.items() if t_id == turn_id]
        if not records:
            records = self._load_turn_manifest(sess_id, turn_id)

        restored_descriptions = []

        for rec in reversed(records):
            try:
                if rec.action == "create":
                    if rec.abs_path.exists():
                        if rec.abs_path.is_file():
                            rec.abs_path.unlink()
                        elif rec.abs_path.is_dir():
                            shutil.rmtree(rec.abs_path, ignore_errors=True)
                        restored_descriptions.append(f"{rec.rel_path} (已删除新建文件)")
                elif rec.action == "modify":
                    if rec.backup_path and rec.backup_path.exists():
                        rec.abs_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(rec.backup_path, rec.abs_path)
                        restored_descriptions.append(f"{rec.rel_path} (已还原)")
            except Exception as e:
                logger.error(f"还原文件 '{rec.rel_path}' 失败: {e}")
                restored_descriptions.append(f"{rec.rel_path} (还原失败: {e})")

        # 清除该轮在内存中的记录与磁盘目录
        to_del = [k for k in self._turn_records.keys() if k[0] == turn_id]
        for k in to_del:
            del self._turn_records[k]

        turn_dir = self.get_turn_dir(sess_id, turn_id)
        if turn_dir.exists():
            shutil.rmtree(turn_dir, ignore_errors=True)

        return restored_descriptions

    def clear_session_snapshots(self, session_id: Optional[str] = None):
        """清空指定会话的快照目录"""
        sess_id = session_id or self.active_session_id
        self._turn_records.clear()
        sess_dir = self.base_snapshot_dir / f"session_{sess_id}"
        if sess_dir.exists():
            shutil.rmtree(sess_dir, ignore_errors=True)

class PatchTransaction:
    """
    单次 apply_patch 的事务保护：
    在执行单次补丁前记录被触碰文件的原始内容；
    若任何一个文件或块在替换过程中失败，立即还原已修改的文件，保证磁盘原子性。
    """
    def __init__(self, snapshot_mgr: Optional[SnapshotManager] = None):
        self.snapshot_mgr = snapshot_mgr or default_snapshot_manager
        # 记录事务开始前状态: {abs_path: (existed, original_content_str)}
        self._pre_states: Dict[Path, Tuple[bool, Optional[str]]] = {}
        self.committed = False

    def record_before_touch(self, file_path: Union[str, Path]):
        abs_path = Path(file_path).resolve()
        if abs_path in self._pre_states:
            return

        # 同步告知轮次快照管理器进行持久化快照（供后续可能的 /undo 回滚使用）
        self.snapshot_mgr.backup_before_mutation(abs_path)

        if abs_path.exists() and abs_path.is_file():
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    self._pre_states[abs_path] = (True, f.read())
            except Exception:
                self._pre_states[abs_path] = (True, None)
        else:
            self._pre_states[abs_path] = (False, None)

    def commit(self):
        """提交事务，清空暂存的本操作回滚态"""
        self.committed = True
        self._pre_states.clear()

    def rollback(self):
        """回滚本事务内修改过的所有文件至开始前状态"""
        for abs_path, (existed, content) in self._pre_states.items():
            try:
                if existed:
                    if content is not None:
                        abs_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(abs_path, "w", encoding="utf-8") as f:
                            f.write(content)
                else:
                    if abs_path.exists():
                        abs_path.unlink()
            except Exception as e:
                logger.error(f"事务回滚文件 '{abs_path}' 失败: {e}")
        self._pre_states.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and not self.committed:
            self.rollback()

default_snapshot_manager = SnapshotManager()
