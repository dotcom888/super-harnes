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
        """验证 /api/workspaces 自动扫描全部 4 个项目的历史"""
        response = self.client.get("/api/workspaces")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("projects", data)
        proj_names = [p["name"] for p in data["projects"]]
        self.assertIn("super-harnes", proj_names)
        self.assertIn("ceshi", proj_names)
        self.assertIn("openclaw-main", proj_names)
        self.assertNotIn("Administrator", proj_names)

    def test_session_turns_cross_project(self):
        """验证跨项目历史轮次精准还原"""
        # 读取 ceshi 项目
        response = self.client.get("/api/sessions/turns?session_id=default&project=ceshi")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("project"), "ceshi")
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
        test_history_dir = Path("history") / test_proj_name
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

        test_dir = Path("history") / "super-harnes"
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
            response = self.client.get(f"/api/sessions/turns?session_id={test_sid}&project=super-harnes")
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

if __name__ == "__main__":
    unittest.main()
