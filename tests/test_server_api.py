# -*- coding: utf-8 -*-
"""
tests/test_server_api.py: 桌面端 FastAPI 后端服务单元测试
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import unittest
from starlette.testclient import TestClient
from server.app import app

class TestServerAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_status_endpoint(self):
        """验证 /api/status 系统状态接口"""
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("ready"))
        self.assertIn("workspace_path", data)
        self.assertIn("model", data)

    def test_models_endpoint(self):
        """验证 /api/models 仅返回有效配置的模型列表"""
        response = self.client.get("/api/models")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("current_model", data)
        self.assertIn("models", data)
        self.assertIn("gemini-3.8-flash-high", data["models"])
        # 确认未配置的虚假模型已被过滤
        self.assertNotIn("claude-3-5-sonnet-20241022", data["models"])

    def test_providers_endpoint(self):
        """验证 /api/models/providers 接口与自定义模型新增功能"""
        initial_cfg_path = ROOT_DIR / "config" / "models_config.json"
        initial_backup = initial_cfg_path.read_text(encoding="utf-8") if initial_cfg_path.exists() else None

        try:
            response = self.client.get("/api/models/providers")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("providers", data)

            # 测试添加自定义提供方 (显式传递 test_temp_id 并立即清理)
            test_pid = "test_temp_id"
            add_resp = self.client.post("/api/models/providers", json={
                "id": test_pid,
                "name": "测试临时提供方",
                "base_url": "https://api.test.example/v1",
                "api_key": "sk-test123456",
                "models": ["test-model-alpha"],
                "is_custom": True
            })
            self.assertEqual(add_resp.status_code, 200)
            self.assertIn("test-model-alpha", add_resp.json().get("active_models", []))

            # 恢复清理测试添加的项
            clean_resp = self.client.delete(f"/api/models/providers/{test_pid}")
            self.assertEqual(clean_resp.status_code, 200)
        finally:
            if initial_backup is not None:
                initial_cfg_path.write_text(initial_backup, encoding="utf-8")

    def test_workspaces_multi_project(self):
        """验证 /api/workspaces 自动扫描已发现项目的历史"""
        response = self.client.get("/api/workspaces")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("projects", data)
        proj_names = [p["name"] for p in data["projects"]]
        self.assertIn("Heim", proj_names)
        self.assertNotIn("Administrator", proj_names)

    def test_session_turns_cross_project(self):
        """验证跨项目历史轮次精准还原"""
        # 读取 Heim 项目真实历史会话
        response = self.client.get("/api/sessions/turns?session_id=session_1791775241917&project=Heim")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("project"), "Heim")
        self.assertTrue(data.get("turns_count") > 0)

    def test_mode_endpoint(self):
        """验证 AUTO / ASK 安全策略模式接口"""
        response = self.client.get("/api/mode")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn(data.get("current_mode"), ["auto", "ask"])

    def test_workspace_deletion_lifecycle(self):
        """测试工作区删除完整性：删除工作区、历史物理移除及黑名单永久过滤"""
        from pathlib import Path
        import json

        # 创建一个临时测试工作区目录与历史记录
        import time
        test_proj_name = f"test_del_proj_{int(time.time() * 1000)}"
        from server.app import HISTORY_ROOT
        test_history_dir = HISTORY_ROOT / test_proj_name
        test_history_dir.mkdir(parents=True, exist_ok=True)
        (test_history_dir / "sessions.jsonl").write_text(
            json.dumps({"type": "session_meta", "session_id": "test_s1", "created_at": 1700000000}) + "\n",
            encoding="utf-8"
        )

        # 验证该工作区可被扫描到
        resp_before = self.client.get("/api/workspaces")
        proj_names_before = [p["name"] for p in resp_before.json().get("projects", [])]
        self.assertIn(test_proj_name, proj_names_before)

        # 执行删除
        del_resp = self.client.request("DELETE", "/api/workspaces/delete", json={"name": test_proj_name})
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.json().get("success"))

        # 验证删除后已不在工作区列表中
        resp_after = self.client.get("/api/workspaces")
        proj_names_after = [p["name"] for p in resp_after.json().get("projects", [])]
        self.assertNotIn(test_proj_name, proj_names_after)

        # 验证物理历史目录已被清理
        self.assertFalse(test_history_dir.exists())


    def test_parse_turns_no_turn_zero_and_title_retention(self):
        """验证修复：解析历史轮次时彻底过滤虚假 turn-0，并保留真实目标与提问"""
        from pathlib import Path
        import json
        import time

        from server.app import HISTORY_ROOT
        test_dir = HISTORY_ROOT / "super-harness"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_sid = f"test_mock_turn0_{int(time.time() * 1000)}"
        mock_file = test_dir / f"{test_sid}.jsonl"

        # 写入带有 turn_id: 0 (session_cleared) 的脏数据及正常轮次
        lines = [
            json.dumps({"timestamp": 1000, "session_id": test_sid, "turn_id": 0, "type": "session_cleared", "data": {"turn_count": 0}}),
            json.dumps({"timestamp": 1001, "session_id": test_sid, "turn_id": 1, "type": "assistant_message", "data": {"role": "assistant", "content": "已在桌面成功创建扫雷游戏"}}),
            json.dumps({"timestamp": 1002, "session_id": test_sid, "turn_id": 1, "type": "turn_finished", "data": {"turn_id": 1, "working_memory": {"current_goal": "在桌面创建一个极简扫雷小游戏"}}})
        ]
        mock_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        try:
            response = self.client.get(f"/api/sessions/turns?session_id={test_sid}&project=super-harness")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            turn_ids = [t["turn_id"] for t in data.get("turns", [])]
            # 绝不出现 turn-0
            self.assertNotIn(0, turn_ids)
            self.assertIn(1, turn_ids)
            # 提问文本被正确恢复
            first_turn = data["turns"][0]
            self.assertTrue(len(first_turn["user_prompt"]) > 0)
            self.assertIn("极简扫雷", first_turn["user_prompt"])
        finally:
            if mock_file.exists():
                mock_file.unlink()

    def test_attachments_storage_and_legacy_migration(self):
        """验证附件存储于 .super-harness/attachments/ 以及旧版 .super_attachments 自动平滑迁移"""
        from tools.framework.workspace import default_workspace
        from server.app import migrate_legacy_attachments

        ws_root = default_workspace.root
        test_sid = "test_att_session"

        # 1. 测试旧版 .super_attachments 目录自动迁移
        legacy_dir = ws_root / ".super_attachments" / test_sid
        legacy_dir.mkdir(parents=True, exist_ok=True)
        legacy_file = legacy_dir / "legacy_test.txt"
        legacy_file.write_text("legacy attachment content", encoding="utf-8")

        migrate_legacy_attachments(ws_root)

        # 验证旧目录已被移除，文件已迁移到 .super-harness/attachments/
        self.assertFalse(legacy_dir.exists())
        migrated_file = ws_root / ".super-harness" / "attachments" / test_sid / "legacy_test.txt"
        self.assertTrue(migrated_file.exists())
        self.assertEqual(migrated_file.read_text(encoding="utf-8"), "legacy attachment content")

        # 2. 测试上传接口落盘到 .super-harness/attachments/
        upload_resp = self.client.post(
            "/api/attachments/upload",
            data={"session_id": test_sid},
            files={"files": ("uploaded_note.txt", b"hello new attachment", "text/plain")}
        )
        self.assertEqual(upload_resp.status_code, 200)
        att_data = upload_resp.json().get("attachments", [])
        self.assertEqual(len(att_data), 1)
        saved_path = Path(att_data[0]["path"])
        self.assertTrue(".super-harness" in str(saved_path))
        self.assertTrue("attachments" in str(saved_path))
        self.assertTrue(saved_path.exists())

        # 3. 测试删除会话清理附件
        del_resp = self.client.request("DELETE", "/api/sessions/delete", json={"session_id": test_sid})
        self.assertEqual(del_resp.status_code, 200)
        session_att_dir = ws_root / ".super-harness" / "attachments" / test_sid
        self.assertFalse(session_att_dir.exists())

    def test_session_delete_query_params_and_post_and_fallback(self):
        """验证删除会话接口通过 Query 参数、POST 方法以及跨目录兜底搜索物理删除"""
        from server.app import HISTORY_ROOT

        # 1. 创建测试会话文件在 _general 目录
        gen_dir = HISTORY_ROOT / "_general"
        gen_dir.mkdir(parents=True, exist_ok=True)
        test_sid_query = "test_del_query_session"
        test_file = gen_dir / f"{test_sid_query}.jsonl"
        test_file.write_text("test_turn", encoding="utf-8")
        self.assertTrue(test_file.exists())

        # 通过 DELETE 请求携带 Query 参数删除（模拟请求体被剥离场景）
        del_resp = self.client.request(
            "DELETE",
            f"/api/sessions/delete?session_id={test_sid_query}&project=_general"
        )
        self.assertEqual(del_resp.status_code, 200)
        self.assertFalse(test_file.exists())

        # 2. 测试 POST 方法与跨目录兜底清理
        proj_dir = HISTORY_ROOT / "TestProjFallback"
        proj_dir.mkdir(parents=True, exist_ok=True)
        test_sid_fallback = "test_del_fallback_session"
        fb_file = proj_dir / f"{test_sid_fallback}.jsonl"
        fb_file.write_text("test_fallback", encoding="utf-8")
        self.assertTrue(fb_file.exists())

        # 即使前端传入了错误的 project 名称，后端也能全盘搜索并安全删除
        post_resp = self.client.post(
            "/api/sessions/delete",
            json={"session_id": test_sid_fallback, "project": "WrongProjectName"}
        )
        self.assertEqual(post_resp.status_code, 200)
        self.assertFalse(fb_file.exists())

        # 清理测试目录
        if proj_dir.exists():
            import shutil
            shutil.rmtree(proj_dir, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()

