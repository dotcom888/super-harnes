# -*- coding: utf-8 -*-
"""
skills/installer.py: 技能安装器，支持从 GitHub 仓库或本地目录安装规范技能
"""
import os
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Union
from skills.skill import Skill, parse_skill_from_directory
from skills.manager import default_skill_manager
from tools.framework.workspace import default_workspace


class SkillInstaller:
    """负责将外部技能拉取或复制到本地工作区或用户目录"""

    @classmethod
    def install_from_local(
        cls,
        source_dir: Union[str, Path],
        dest_dir: Optional[Union[str, Path]] = None,
        name: Optional[str] = None,
        target_scope: str = "workspace"
    ) -> Skill:
        """从本地现有目录安装技能"""
        src = Path(source_dir).resolve()
        if not src.exists() or not src.is_dir():
            raise FileNotFoundError(f"源技能目录不存在: {src}")

        skill_file = src / "SKILL.md"
        if not skill_file.exists():
            skill_file = src / "skill.md"
        if not skill_file.exists():
            raise ValueError(f"源目录未包含 SKILL.md 规范文件: {src}")

        # 确定目标目录
        if dest_dir:
            dest_root = Path(dest_dir).resolve()
        elif target_scope == "workspace":
            dest_root = default_workspace.root / ".skills"
        else:
            dest_root = Path.home() / ".agents" / "skills"

        dest_root.mkdir(parents=True, exist_ok=True)
        
        # 优先从元数据解析技能标识，避免文件夹名与技能名不一致
        if not name:
            parsed_initial = parse_skill_from_directory(src)
            skill_name = parsed_initial.name if parsed_initial else src.name
        else:
            skill_name = name

        target_dir = dest_root / skill_name

        if target_dir.exists():
            shutil.rmtree(target_dir)

        shutil.copytree(src, target_dir)
        default_skill_manager.reload()

        installed = default_skill_manager.get_skill(skill_name)
        if not installed:
            # 若安装在自定义独立路径，直接解析该目录并手动登记
            installed = parse_skill_from_directory(target_dir, source_scope="custom")
            if installed:
                default_skill_manager.register_custom_skill(installed)

        if not installed:
            raise RuntimeError(f"安装后未能成功索引技能: {skill_name}")
        return installed

    @classmethod
    def install_from_github(
        cls,
        repo: str,
        path: Optional[str] = None,
        dest_dir: Optional[Union[str, Path]] = None,
        name: Optional[str] = None,
        ref: str = "main",
        target_scope: str = "workspace"
    ) -> Skill:
        """
        从远程 GitHub 仓库安装指定技能。
        :param repo: "owner/repo" 或完整 https://github.com/owner/repo url
        :param path: 仓库内的相对路径，例如 "skills/engineering/diagnosing-bugs"
        """
        if repo.startswith("https://github.com/"):
            repo_clean = repo.replace("https://github.com/", "").strip("/").removesuffix(".git")
        else:
            repo_clean = repo.strip("/")

        clone_url = f"https://github.com/{repo_clean}.git"
        temp_dir = Path(tempfile.mkdtemp(prefix="harnes_skill_"))
        try:
            # 浅克隆以极快拉取代码
            cmd = ["git", "clone", "--depth", "1", "--branch", ref, clone_url, str(temp_dir)]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode != 0:
                # 尝试默认分支
                cmd = ["git", "clone", "--depth", "1", clone_url, str(temp_dir)]
                res = subprocess.run(cmd, capture_output=True, text=True, check=True)

            src_path = temp_dir
            if path:
                src_path = temp_dir / Path(path)

            if not src_path.exists():
                raise FileNotFoundError(f"在仓库 {repo_clean} 中未找到路径: {path}")

            skill_name = name or (Path(path).name if path else Path(repo_clean).name)
            return cls.install_from_local(
                source_dir=src_path,
                dest_dir=dest_dir,
                name=skill_name,
                target_scope=target_scope
            )
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
