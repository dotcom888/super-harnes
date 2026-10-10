import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("super-server.project_utils")

# 服务端代码自身的物理根目录
AGENT_SOURCE_ROOT = Path(__file__).resolve().parents[1]
HISTORY_ROOT = AGENT_SOURCE_ROOT / "history"
PROJECTS_CONFIG_FILE = Path.home() / ".super-harnes" / "projects.json"
PINS_CONFIG_FILE = HISTORY_ROOT / "pins_config.json"

def get_registered_projects() -> list:
    """读取 ~/.super-harnes/projects.json 中注册的磁盘项目映射"""
    if PROJECTS_CONFIG_FILE.exists():
        try:
            with open(PROJECTS_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning(f"Failed to read projects.json: {e}")
    return []

def save_registered_projects(projects: list) -> None:
    """持久化保存 ~/.super-harnes/projects.json"""
    PROJECTS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROJECTS_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)

def resolve_project_workspace_root(project_name: str) -> Path:
    """
    全方位解析项目工作区的真实物理路径，支持大小写自适应与自动探测：
    1. 优先读取 history/<project_name>/project_state.json 的 workspace_root
    2. 检索 ~/.super-harnes/projects.json 中注册的物理路径 (不区分大小写匹配)
    3. 自动探测同级目录 (例如 E:\\study\\<project_name>)
    4. 若为 super-harnes 本身，返回 AGENT_SOURCE_ROOT
    5. 兜底回退：在 ~/.super-harnes/workspace/<project_name> 创建独立项目根目录
    """
    pname_clean = project_name.strip()
    pname_lower = pname_clean.lower()

    # 1. 尝试从 history/ 对应的 project_state.json 读取
    target_history_dir = HISTORY_ROOT / pname_clean
    if not target_history_dir.exists():
        # 在 Windows 上不区分大小写查找对应目录
        for d in HISTORY_ROOT.iterdir():
            if d.is_dir() and d.name.lower() == pname_lower:
                target_history_dir = d
                break

    ps_file = target_history_dir / "project_state.json"
    if ps_file.exists():
        try:
            with open(ps_file, "r", encoding="utf-8") as f:
                ps_data = json.load(f)
                ws_root = ps_data.get("workspace_root")
                if ws_root:
                    p = Path(ws_root).resolve()
                    if p.exists() and p.is_dir():
                        return p
        except Exception:
            pass

    # 2. 检查 ~/.super-harnes/projects.json 注册表
    registered = get_registered_projects()
    for reg in registered:
        r_name = str(reg.get("name", "")).strip()
        r_path = str(reg.get("path", "")).strip()
        if r_name.lower() == pname_lower and r_path:
            p = Path(r_path).resolve()
            if p.exists() and p.is_dir():
                # 顺便回写到 project_state.json 以保证一致性
                _persist_project_state(target_history_dir, pname_clean, str(p))
                return p

    # 3. 自动在父级目录或同级目录寻找同名文件夹 (例如 E:\study\ECoHarvest)
    parent_dir = AGENT_SOURCE_ROOT.parent
    if parent_dir.exists():
        for sibling in parent_dir.iterdir():
            if sibling.is_dir() and sibling.name.lower() == pname_lower:
                found_path = sibling.resolve()
                # 登记到 projects.json 与 project_state.json
                register_project_path(pname_clean, str(found_path))
                _persist_project_state(target_history_dir, pname_clean, str(found_path))
                return found_path

    # 4. 若名称为 super-harnes 则直接为自身代码根目录
    if pname_lower in ("super-harnes", "super-server"):
        return AGENT_SOURCE_ROOT

    # 5. 兜底：分配独立的专属用户工程目录，严禁指向 super-harnes 源码
    fallback_dir = Path.home() / ".super-harnes" / "workspace" / pname_clean
    fallback_dir.mkdir(parents=True, exist_ok=True)
    register_project_path(pname_clean, str(fallback_dir))
    _persist_project_state(target_history_dir, pname_clean, str(fallback_dir))
    return fallback_dir

def _persist_project_state(proj_dir: Path, proj_name: str, ws_path: str):
    """将项目绑定状态写入 project_state.json"""
    try:
        proj_dir.mkdir(parents=True, exist_ok=True)
        ps_file = proj_dir / "project_state.json"
        data = {}
        if ps_file.exists():
            try:
                with open(ps_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        data["project_name"] = proj_name
        data["workspace_root"] = ws_path
        with open(ps_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to persist project_state for {proj_name}: {e}")

def register_project_path(name: str, path: str):
    """将新项目或更新路径登记到 ~/.super-harnes/projects.json"""
    projects = get_registered_projects()
    norm_path = str(Path(path).resolve())
    updated = False
    for p in projects:
        if str(p.get("name", "")).lower() == name.lower():
            p["name"] = name
            p["path"] = norm_path
            updated = True
            break
    if not updated:
        projects.append({"name": name, "path": norm_path})
    save_registered_projects(projects)
