import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from tools.framework.workspace import atomic_write_text

logger = logging.getLogger(__name__)

class GlobalMemory:
    """
    用户级全局共享记忆 (Global User Memory):
    位于操作系统的用户主目录 (~/.super-harnes/global_memory.json)。
    跨越所有项目工程生效，永久保留：
    1. 用户编码偏好与开发规范 (user_profile.coding_habits)
    2. 交互语言与回复风格 (user_profile.language, interaction_preference)
    3. 历史/已登记项目工作区索引地图 (project_registry)
    """
    def __init__(self, storage_path: Optional[Union[str, Path]] = None):
        if storage_path:
            self.storage_path = Path(storage_path).resolve()
        else:
            self.storage_path = (Path.home() / ".super-harnes" / "global_memory.json").resolve()

        self.version = "1.0"
        self.updated_at = time.time()
        self.user_profile: Dict[str, Any] = {
            "language": "简体中文",
            "coding_habits": [
                "Python 函数建议标注类型注解 (Type Hints) 并保持清晰签名",
                "代码排查与重构前优先提取文件大纲，定位明确后再动代码"
            ],
            "interaction_preference": [
                "回答风格保持精炼直接、结论先行，避免过多废话"
            ]
        }
        self.project_registry: Dict[str, Dict[str, Any]] = {}

        if self.storage_path.exists():
            self.load_from_disk()
        else:
            self.save_to_disk()

    def load_from_disk(self):
        """从磁盘反序列化全局记忆文件"""
        if not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.version = data.get("version", "1.0")
            self.updated_at = data.get("updated_at", time.time())
            loaded_profile = data.get("user_profile", {})
            if isinstance(loaded_profile, dict):
                if "language" in loaded_profile:
                    self.user_profile["language"] = str(loaded_profile["language"])
                if "coding_habits" in loaded_profile and isinstance(loaded_profile["coding_habits"], list):
                    self.user_profile["coding_habits"] = [str(x) for x in loaded_profile["coding_habits"]]
                if "interaction_preference" in loaded_profile and isinstance(loaded_profile["interaction_preference"], list):
                    self.user_profile["interaction_preference"] = [str(x) for x in loaded_profile["interaction_preference"]]

            loaded_registry = data.get("project_registry", {})
            if isinstance(loaded_registry, dict):
                self.project_registry = loaded_registry
        except Exception as e:
            logger.warning(f"读取全局记忆文件失败 ({self.storage_path}): {e}")

    def save_to_disk(self):
        """原子落盘全局记忆文件"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.updated_at = time.time()
            data = {
                "version": self.version,
                "updated_at": self.updated_at,
                "user_profile": self.user_profile,
                "project_registry": self.project_registry
            }
            atomic_write_text(self.storage_path, json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.warning(f"保存全局记忆文件失败 ({self.storage_path}): {e}")

    def add_habit(self, habit_text: str) -> bool:
        """添加一条编码偏好/开发规范"""
        clean_text = str(habit_text).strip()
        if not clean_text:
            return False
        habits = self.user_profile.setdefault("coding_habits", [])
        if clean_text not in habits:
            habits.append(clean_text)
            self.save_to_disk()
            return True
        return False

    def remove_habit(self, keyword: str) -> List[str]:
        """按关键字移除编码习惯"""
        kw = str(keyword).strip().lower()
        if not kw:
            return []
        habits = self.user_profile.get("coding_habits", [])
        removed = []
        kept = []
        for h in habits:
            if kw in h.lower():
                removed.append(h)
            else:
                kept.append(h)
        if removed:
            self.user_profile["coding_habits"] = kept
            self.save_to_disk()
        return removed

    def add_preference(self, pref_text: str) -> bool:
        """添加一条交互风格偏好"""
        clean_text = str(pref_text).strip()
        if not clean_text:
            return False
        prefs = self.user_profile.setdefault("interaction_preference", [])
        if clean_text not in prefs:
            prefs.append(clean_text)
            self.save_to_disk()
            return True
        return False

    def set_language(self, lang: str):
        """设置默认回复语言"""
        clean_lang = str(lang).strip()
        if clean_lang:
            self.user_profile["language"] = clean_lang
            self.save_to_disk()

    def register_project(self, name: str, path: Union[str, Path], description: str = ""):
        """登记或更新一个本地项目工作区索引"""
        clean_name = str(name).strip()
        if not clean_name:
            return
        abs_path = str(Path(path).resolve())
        entry = self.project_registry.get(clean_name, {})
        entry["path"] = abs_path
        if description:
            entry["description"] = description
        elif "description" not in entry:
            entry["description"] = f"本地工程 {clean_name}"
        entry["last_accessed"] = time.time()
        self.project_registry[clean_name] = entry
        self.save_to_disk()

    def get_project(self, name_or_alias: str) -> Optional[Dict[str, Any]]:
        """按名称查找登记的项目"""
        query = str(name_or_alias).strip().lower()
        for p_name, meta in self.project_registry.items():
            if p_name.lower() == query or Path(meta.get("path", "")).name.lower() == query:
                return {"name": p_name, **meta}
        return None

    def list_projects(self) -> List[Dict[str, Any]]:
        """获取所有登记的项目列表，按最近访问时间倒序排列"""
        res = []
        for p_name, meta in self.project_registry.items():
            res.append({
                "name": p_name,
                "path": meta.get("path", ""),
                "description": meta.get("description", ""),
                "last_accessed": meta.get("last_accessed", 0)
            })
        res.sort(key=lambda x: -x["last_accessed"])
        return res

    def format_prompt_context(self) -> str:
        """
        格式化为注入 System Prompt 的紧凑纯文本（Prompt Cache 友好，仅消耗数十 Tokens）
        """
        lines = ["### 用户全局偏好与开发规范 (User Global Profile):"]
        lang = self.user_profile.get("language", "简体中文")
        prefs = self.user_profile.get("interaction_preference", [])
        pref_str = " | ".join(prefs) if prefs else "精炼直接、结论先行"
        lines.append(f"- 交互语言: {lang} | 交互偏好: {pref_str}")

        habits = self.user_profile.get("coding_habits", [])
        if habits:
            lines.append("- 编码习惯与开发规范:")
            for h in habits[:6]:
                lines.append(f"  • {h}")

        return "\n".join(lines)

    def format_profile_view(self) -> str:
        """生成控制台展示看板"""
        lines = [f"\n{'='*22} 用户全局共享记忆 (~/.super-harnes) {'='*22}"]
        lines.append(f"• 交互语言: {self.user_profile.get('language', '简体中文')}")
        prefs = self.user_profile.get("interaction_preference", [])
        if prefs:
            lines.append("• 交互偏好:")
            for p in prefs:
                lines.append(f"  - {p}")
        habits = self.user_profile.get("coding_habits", [])
        lines.append(f"• 编码习惯与开发规范 ({len(habits)} 条):")
        for i, h in enumerate(habits, 1):
            lines.append(f"  {i}. {h}")

        projs = self.list_projects()
        lines.append(f"\n• 已登记工程工作区 ({len(projs)} 个):")
        for p in projs[:8]:
            lines.append(f"  - 【{p['name']}】: {p['path']} ({p['description']})")
        if len(projs) > 8:
            lines.append(f"  ... [早期项目省略 {len(projs)-8} 个]")

        lines.append("="*66)
        lines.append("💡 提示: /remember <规范> 添加偏好，/forget <词> 移除偏好，/projects 查看项目。")
        return "\n".join(lines)

# 全局默认单例
default_global_memory = GlobalMemory()
