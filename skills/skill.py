# -*- coding: utf-8 -*-
"""
skills/skill.py: Agent 技能 (Skill) 数据模型与 Frontmatter 解析引擎
遵循行业通用的 SKILL.md 规范 (OpenAI / Claude Code / skills.sh 兼容)
"""
import re
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import yaml
except ImportError:
    yaml = None


class Skill:
    """
    表示一个领域专家技能 (Skill) 实体
    由包含 SKILL.md 的独立目录定义，包含结构化元数据与可执行的工程 SOP
    """
    def __init__(
        self,
        name: str,
        description: str,
        directory: Path,
        skill_file: Path,
        metadata: Optional[Dict[str, Any]] = None,
        source_scope: str = "workspace",
        raw_content: str = "",
        body_content: str = ""
    ):
        self.name = name.strip()
        self.description = description.strip()
        self.directory = Path(directory).resolve()
        self.skill_file = Path(skill_file).resolve()
        self.metadata = metadata or {}
        self.source_scope = source_scope  # "workspace", "user", "builtin", "custom"
        self._raw_content = raw_content
        self._body_content = body_content

    @property
    def content(self) -> str:
        """获取去掉 YAML Frontmatter 后的纯 SOP 规约正文"""
        if not self._body_content and self.skill_file.exists():
            self._load_from_disk()
        return self._body_content

    @property
    def raw_content(self) -> str:
        """获取包含 YAML Frontmatter 的完整 SKILL.md 内容"""
        if not self._raw_content and self.skill_file.exists():
            self._load_from_disk()
        return self._raw_content

    def _load_from_disk(self):
        try:
            text = self.skill_file.read_text(encoding="utf-8", errors="replace")
            self._raw_content = text
            meta, body = parse_frontmatter(text)
            self._body_content = body
            if not self.metadata:
                self.metadata = meta
        except Exception:
            self._raw_content = ""
            self._body_content = ""

    def get_summary(self) -> str:
        """获取单行摘要"""
        desc = self.description.replace("\n", " ").strip()
        if len(desc) > 80:
            desc = desc[:77] + "..."
        return f"{self.name} [{self.source_scope}]: {desc}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "directory": str(self.directory),
            "skill_file": str(self.skill_file),
            "source_scope": self.source_scope,
            "metadata": self.metadata
        }

    def __repr__(self) -> str:
        return f"<Skill name='{self.name}' scope='{self.source_scope}' path='{self.directory}'>"


def parse_frontmatter(text: str) -> tuple[Dict[str, Any], str]:
    """
    解析 Markdown 文件头部的 YAML Frontmatter。
    返回: (metadata_dict, body_markdown)
    """
    pattern = r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n(.*)$"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return {}, text.strip()

    fm_raw = match.group(1).strip()
    body = match.group(2).strip()

    metadata: Dict[str, Any] = {}
    if yaml is not None:
        try:
            parsed = yaml.safe_load(fm_raw)
            if isinstance(parsed, dict):
                metadata = parsed
        except Exception:
            metadata = _fallback_parse_yaml(fm_raw)
    else:
        metadata = _fallback_parse_yaml(fm_raw)

    return metadata, body


def _fallback_parse_yaml(fm_text: str) -> Dict[str, Any]:
    """轻量级正则解析器，用于缺乏 PyYAML 或 YAML 格式微损时的安全回退"""
    data = {}
    current_key = None
    multiline_buf = []

    for line in fm_text.splitlines():
        # 简单 key: value
        kv_match = re.match(r"^([a-zA-Z0-9_\-]+)\s*:\s*(.*)$", line)
        if kv_match:
            if current_key and multiline_buf:
                data[current_key] = " ".join(multiline_buf).strip()
                multiline_buf = []
            key = kv_match.group(1)
            val = kv_match.group(2).strip()
            # 去除引号
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            if val in (">", "|", ""):
                current_key = key
            else:
                data[key] = val
                current_key = None
        elif current_key and line.startswith("  "):
            multiline_buf.append(line.strip())

    if current_key and multiline_buf:
        data[current_key] = " ".join(multiline_buf).strip()

    return data


def parse_skill_from_directory(directory: Path, source_scope: str = "workspace") -> Optional[Skill]:
    """
    从指定目录中探测并解析 SKILL.md，构建 Skill 实例
    """
    dir_path = Path(directory).resolve()
    if not dir_path.is_dir():
        return None

    # 支持 SKILL.md / skill.md
    skill_file = dir_path / "SKILL.md"
    if not skill_file.exists():
        skill_file = dir_path / "skill.md"
    if not skill_file.exists():
        return None

    try:
        raw_text = skill_file.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    meta, body = parse_frontmatter(raw_text)

    # 提取 name
    name = meta.get("name") or dir_path.name
    name = str(name).strip()

    # 提取 description
    desc = meta.get("description") or ""
    if not desc and body:
        # 取正文第一个非标题非空行
        for line in body.splitlines():
            line_s = line.strip()
            if line_s and not line_s.startswith("#"):
                desc = line_s
                break
    if not desc:
        desc = f"关于 {name} 的专业工程操作规范与流程。"

    return Skill(
        name=name,
        description=str(desc).strip(),
        directory=dir_path,
        skill_file=skill_file,
        metadata=meta,
        source_scope=source_scope,
        raw_content=raw_text,
        body_content=body
    )
