# -*- coding: utf-8 -*-
import importlib
import pkgutil
from pathlib import Path
from tools.framework.registry import default_registry, register_tool, ToolRegistry
from tools.framework.executor import ToolExecutor, default_executor
from tools.framework.policies import CommandPolicy, PolicyDecision, default_policy

def _auto_discover_builtin_tools():
    builtin_dir = Path(__file__).parent / "builtin"
    if builtin_dir.exists():
        for module_info in pkgutil.iter_modules([str(builtin_dir)]):
            importlib.import_module(f"tools.builtin.{module_info.name}")

_auto_discover_builtin_tools()

registry = default_registry

__all__ = [
    "registry",
    "register_tool",
    "ToolRegistry",
    "ToolExecutor",
    "default_executor",
    "CommandPolicy",
    "PolicyDecision",
    "default_policy"
]
