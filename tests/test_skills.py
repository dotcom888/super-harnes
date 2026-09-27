# -*- coding: utf-8 -*-
import pytest
from pathlib import Path
import tempfile
import shutil
from skills.skill import Skill, parse_frontmatter, parse_skill_from_directory
from skills.manager import SkillManager
from skills.installer import SkillInstaller
from tools.builtin.skill_tools import load_skill, list_available_skills
from core.prompt import build_system_prompt
from cli.commands import handle_slash_command
from unittest.mock import MagicMock


def test_frontmatter_parsing():
    sample_text = """---
name: code-review
description: 针对代码变更的架构与风格审查 SOP
type: engineering
---

# Code Review Process

## Step 1
Check git diff carefully.
"""
    meta, body = parse_frontmatter(sample_text)
    assert meta["name"] == "code-review"
    assert meta["description"] == "针对代码变更的架构与风格审查 SOP"
    assert meta["type"] == "engineering"
    assert "# Code Review Process" in body
    assert "Check git diff carefully." in body


def test_frontmatter_parsing_fallback():
    # 没有 frontmatter 的纯 markdown
    plain_text = "# Just Title\n\nSome plain content."
    meta, body = parse_frontmatter(plain_text)
    assert meta == {}
    assert "Just Title" in body


def test_skill_from_directory(tmp_path):
    skill_dir = tmp_path / "mock-skill"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("""---
name: mock-skill
description: 用于测试的模拟技能
---
## Execution Rules
Always test before shipping.
""", encoding="utf-8")

    skill = parse_skill_from_directory(skill_dir, source_scope="workspace")
    assert skill is not None
    assert skill.name == "mock-skill"
    assert skill.description == "用于测试的模拟技能"
    assert "Always test before shipping." in skill.content
    assert skill.source_scope == "workspace"


def test_skill_manager_discovery_and_precedence(tmp_path):
    ws_skills = tmp_path / ".skills"
    ws_skills.mkdir(parents=True)
    
    # 模拟工作区技能
    s1_dir = ws_skills / "s1"
    s1_dir.mkdir()
    (s1_dir / "SKILL.md").write_text("""---
name: s1
description: 工作区级别的 S1 技能
---
Body of S1
""", encoding="utf-8")

    mgr = SkillManager(workspace_root=tmp_path)
    mgr._workspace_root = tmp_path
    mgr.reload()

    found = mgr.get_skill("s1")
    assert found is not None
    assert found.name == "s1"
    assert "S1" in found.description
    assert mgr.get_skill("S1") is not None  # 大小写不敏感支持

    catalog = mgr.format_prompt_skills_catalog()
    assert "`s1`" in catalog


def test_builtin_skill_tools():
    # 测试 list_available_skills
    list_res = list_available_skills()
    assert isinstance(list_res, str)
    assert "专家技能" in list_res or "SKILL.md" in list_res

    # 测试 load_skill 存在情况 (以已安装的 diagnosing-bugs 为例)
    load_res = load_skill("diagnosing-bugs")
    assert "diagnosing-bugs" in load_res
    assert "SOP 执行规约" in load_res

    # 测试 load_skill 不存在情况
    err_res = load_skill("non-existent-skill-xyz")
    assert "【未找到技能】" in err_res


def test_prompt_catalog_integration():
    prompt = build_system_prompt()
    assert "Available Agent Skills" in prompt or "load_skill" in prompt


def test_slash_command_skills():
    mock_agent = MagicMock()
    # 测试 /skills
    is_cmd, should_exit = handle_slash_command(mock_agent, "/skills")
    assert is_cmd is True
    assert should_exit is False

    # 测试 /skill load
    is_cmd, should_exit = handle_slash_command(mock_agent, "/skill load diagnosing-bugs")
    assert is_cmd is True
    assert should_exit is False


def test_skill_installer_local(tmp_path):
    src_dir = tmp_path / "custom-src"
    src_dir.mkdir()
    (src_dir / "SKILL.md").write_text("""---
name: my-temp-skill
description: 临时安装技能
---
Hello Skill
""", encoding="utf-8")

    dest_dir = tmp_path / "installed_skills"
    installed = SkillInstaller.install_from_local(src_dir, dest_dir=dest_dir)
    assert installed.name == "my-temp-skill"
    assert (dest_dir / "my-temp-skill" / "SKILL.md").exists()
