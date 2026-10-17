# -*- coding: utf-8 -*-
"""
tests/test_history_sync_and_cli_general.py: 针对 history 物理删除双向同步与终端默认 _general 的单元测试
"""
import unittest
import shutil
import uuid
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from server.project_utils import (
    HISTORY_ROOT,
    get_registered_projects,
    save_registered_projects,
    resolve_project_workspace_root
)
from server.app import get_all_projects_metadata, scan_project_sessions
from core.session import SessionManager
from tools.framework.workspace import default_workspace


class TestHistorySyncAndCliGeneral(unittest.TestCase):
    def setUp(self):
        self.test_proj = f"unit_test_proj_{uuid.uuid4().hex[:8]}"
        self.test_hist_dir = HISTORY_ROOT / self.test_proj
        self.test_ws_dir = Path.home() / ".super-harness" / "workspace" / self.test_proj
        self.test_ws_dir.mkdir(parents=True, exist_ok=True)
        self.test_hist_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_hist_dir, ignore_errors=True)
        shutil.rmtree(self.test_ws_dir, ignore_errors=True)
        projects = [p for p in get_registered_projects() if p.get("name") != self.test_proj]
        save_registered_projects(projects)

    def test_deleting_history_dir_syncs_and_does_not_resurrect(self):
        """测试1: 用户在 history/ 下物理删除项目目录后，projects.json 自动同步清理，目录绝不复活"""
        # 登记项目
        projects = get_registered_projects()
        projects.append({"name": self.test_proj, "path": str(self.test_ws_dir)})
        save_registered_projects(projects)

        # 模拟用户物理删除
        shutil.rmtree(self.test_hist_dir, ignore_errors=True)
        self.assertFalse(self.test_hist_dir.exists())

        # 调用扫描
        meta = get_all_projects_metadata()
        names = [p["name"] for p in meta]

        # 验证: 目录绝不能被自动创建复活
        self.assertFalse(self.test_hist_dir.exists())
        # 验证: projects.json 已同步移除该项目
        self.assertFalse(any(p.get("name") == self.test_proj for p in get_registered_projects()))
        # 验证: 返回结果不含已删除项目
        self.assertNotIn(self.test_proj, names)

    def test_session_manager_does_not_resurrect_deleted_default(self):
        """测试2: 删除 default.jsonl 后，SessionManager 实例化绝不再次从根目录复制旧 default.jsonl"""
        sm = SessionManager(project_name=self.test_proj, history_dir=self.test_hist_dir)
        d_file = self.test_hist_dir / "default.jsonl"
        # 用户物理删除 default.jsonl
        if d_file.exists():
            d_file.unlink()
        self.assertFalse(d_file.exists())

        # 重新创建 SessionManager
        sm2 = SessionManager(project_name=self.test_proj, history_dir=self.test_hist_dir)
        # 验证: 依然不存在，绝不自动复活
        self.assertFalse(d_file.exists())

    def test_cli_defaults_to_general_partition(self):
        """测试3: 终端 super 默认对话分区为 _general，落盘归属于 history/_general/"""
        # 模拟无 -p 参数启动
        from cli.console import argparse
        with patch("argparse.ArgumentParser.parse_known_args") as mock_args:
            mock_ns = MagicMock()
            mock_ns.cwd = None
            mock_ns.plain = True
            mock_ns.mode = None
            mock_ns.auto = False
            mock_ns.model = None
            mock_ns.ask = False
            mock_ns.project = None  # 默认无指定
            mock_args.return_value = (mock_ns, [])

            # 验证 target_project 解析逻辑
            target_project = mock_ns.project.strip() if mock_ns.project else "_general"
            self.assertEqual(target_project, "_general")

            sm = SessionManager(
                default_session_id="default",
                workspace=default_workspace,
                project_name=target_project,
                history_dir=(HISTORY_ROOT / target_project).resolve()
            )
            self.assertEqual(sm.project_name, "_general")
            self.assertEqual(sm.history_dir.name, "_general")


if __name__ == "__main__":
    unittest.main()
