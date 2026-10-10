# -*- coding: utf-8 -*-
"""
skills/manager.py: Agent 技能注册与全局发现管理器
支持多级级联扫描（工作区目录 > 用户全局目录 > 兼容目录），按需索引与轻量提示词生成
"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple
from skills.skill import Skill, parse_skill_from_directory
# workspace lazily imported in workspace_root property

logger = logging.getLogger(__name__)


class SkillManager:
    """
    统一管理 Agent 技能的发现、检索与生命周期
    """
    def __init__(self, workspace_root: Optional[Path] = None):
        self._workspace_root = workspace_root
        self._skills: Dict[str, Skill] = {}
        self.reload()

    @property
    def workspace_root(self) -> Optional[Path]:
        if self._workspace_root is not None:
            return self._workspace_root
        try:
            from tools.framework.workspace import default_workspace
            if hasattr(default_workspace, "root"):
                return default_workspace.root
        except Exception:
            pass
        return None

    def _get_candidate_roots(self) -> List[Tuple[Path, str]]:
        """
        按照优先级排序的技能扫描候选根目录列表：
        1. 当前工作区级（最高优先级）：<workspace>/.skills, <workspace>/.agents/skills
        2. 用户全局级（跨 Agent 共享）：~/.agents/skills
        3. Codex / Super-Harnes 兼容级：~/.codex/skills, ~/.super-harnes/skills
        """
        candidates: List[Tuple[Path, str]] = []
        agent_source_root = Path(__file__).resolve().parents[1]

        # 1. super 智能体内核原生搭载的专家技能 SOP (属于系统内置级)
        candidates.append((agent_source_root / ".skills", "builtin"))
        candidates.append((agent_source_root / "skills", "builtin"))

        # 2. 当前工程工作区私有级 (排除智能体自身源码目录)
        ws = self.workspace_root
        if ws and ws.exists() and ws.resolve() != agent_source_root.resolve():
            candidates.append((ws / ".skills", "project"))
            candidates.append((ws / ".agents" / "skills", "project"))
            candidates.append((ws / ".super-harnes" / "skills", "project"))

        # 3. 用户全局宿主机目录 (跨 Agent 共享技能库)
        home = Path.home()
        candidates.append((home / ".agents" / "skills", "user"))
        candidates.append((home / ".super-harnes" / "skills", "user"))
        candidates.append((home / ".codex" / "skills", "codex"))

        return candidates

    def reload(self):
        """重新扫描所有候选路径，更新技能注册表"""
        new_skills: Dict[str, Skill] = {}
        candidate_roots = self._get_candidate_roots()

        for root_dir, scope in candidate_roots:
            if not root_dir.exists() or not root_dir.is_dir():
                continue
            self._scan_directory(root_dir, scope, new_skills)

        self._skills = new_skills
        logger.info(f"[SkillManager] 扫描完成，共索引挂载 {len(self._skills)} 个可用技能。")

    def _scan_directory(self, root_dir: Path, scope: str, result_dict: Dict[str, Skill]):
        """
        扫描目录及其子目录（支持平铺模式及分类归档模式，如 skills/engineering/diagnosing-bugs）
        """
        try:
            entries = list(root_dir.iterdir())
        except Exception:
            return

        for entry in entries:
            if not entry.is_dir() or entry.name.startswith("."):
                continue

            # 1. 尝试直接作为技能目录解析 (如 ~/.agents/skills/diagnosing-bugs/SKILL.md)
            skill = parse_skill_from_directory(entry, source_scope=scope)
            if skill:
                if skill.name not in result_dict:
                    result_dict[skill.name] = skill
                continue

            # 2. 支持二级归档子目录 (如 .skills/engineering/diagnosing-bugs/SKILL.md)
            try:
                sub_entries = list(entry.iterdir())
                for sub_entry in sub_entries:
                    if sub_entry.is_dir() and not sub_entry.name.startswith("."):
                        sub_skill = parse_skill_from_directory(sub_entry, source_scope=scope)
                        if sub_skill and sub_skill.name not in result_dict:
                            result_dict[sub_skill.name] = sub_skill
            except Exception:
                continue

    def list_skills(self) -> List[Skill]:
        """返回已加载技能列表，按名称字母顺序排序"""
        return sorted(self._skills.values(), key=lambda s: s.name.lower())

    def get_skill(self, name: str) -> Optional[Skill]:
        """按名称查找技能（支持大小写不敏感匹配）"""
        if not name:
            return None
        target = name.strip()
        if target in self._skills:
            return self._skills[target]
        target_lower = target.lower()
        for k, v in self._skills.items():
            if k.lower() == target_lower:
                return v
        return None

    def register_custom_skill(self, skill: Skill, overwrite: bool = True):
        """手动动态挂载技能"""
        if skill.name in self._skills and not overwrite:
            return
        self._skills[skill.name] = skill

    def format_prompt_skills_catalog(self) -> str:
        """
        为 System Prompt 格式化极轻量的技能纲要索引列表。
        零额外大文本注入，仅告知模型技能名称及触发场景。
        """
        skills = self.list_skills()
        if not skills:
            return ""

        lines = [
            "### 领域专有工程技能库 (Available Agent Skills & SOPs):",
            "当前系统已挂载以下领域专家工程技能规范。当你需要处理对应复杂场景时，必须先调用 `load_skill(skill_name=\"...\")` 获取该领域的完整执行规范与步骤，严格按 SOP 闭环推进："
        ]
        for skill in skills:
            # 紧凑单行格式
            clean_desc = skill.description.replace("\r", "").replace("\n", " ").strip()
            if len(clean_desc) > 120:
                clean_desc = clean_desc[:117] + "..."
            lines.append(f"- `{skill.name}`: {clean_desc}")

        return "\n".join(lines)


default_skill_manager = SkillManager()
