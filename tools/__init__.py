# -*- coding: utf-8 -*-
import importlib
import pkgutil
from pathlib import Path
from tools.framework.registry import default_registry, register_tool, ToolRegistry
from tools.framework.executor import ToolExecutor, default_executor
from tools.framework.policies import CommandPolicy, PolicyDecision, default_policy
from tools.framework.workspace import (
    WorkspaceContext,
    default_workspace,
    get_workspace_root,
    set_workspace_root,
)
from tools.framework.snapshot import (
    SnapshotManager,
    PatchTransaction,
    default_snapshot_manager,
)

def _auto_discover_builtin_tools():
    builtin_dir = Path(__file__).parent / 'builtin'
    if builtin_dir.exists():
        for module_info in pkgutil.iter_modules([str(builtin_dir)]):
            try:
                importlib.import_module(f'tools.builtin.{module_info.name}')
            except Exception:
                pass
    # 显式导入以确保在 PyInstaller 打包脱机环境下核心内置工具 100% 注册
    for mod in ['file_tools', 'patch_tool', 'search_tools', 'shell_tool', 'skill_tools', 'interaction_tools']:
        try:
            importlib.import_module(f'tools.builtin.{mod}')
        except Exception:
            pass

_auto_discover_builtin_tools()
# 自动将所有原生内置核心工具锁定为不可覆盖，防御恶意或同名 MCP 劫持 (Tool Shadowing)
default_registry.lock_all()

registry = default_registry

__all__ = [
    'registry',
    'register_tool',
    'ToolRegistry',
    'ToolExecutor',
    'default_executor',
    'CommandPolicy',
    'PolicyDecision',
    'default_policy',
    'WorkspaceContext',
    'default_workspace',
    'get_workspace_root',
    'set_workspace_root',
    'SnapshotManager',
    'PatchTransaction',
    'default_snapshot_manager',
]
