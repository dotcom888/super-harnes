# -*- coding: utf-8 -*-
"""
tools/__init__.py:
本地内置核心工具加载入口。
原则：仅注册严苛沙箱环境下的核心代码工程工具 (read_file, apply_patch, run_shell, grep, find)。
外围扩展业务工具（如计算器、系统环境探测）统一剥离并通过 MCP 协议外接。
"""
import importlib
from tools.registry import default_registry, register_tool

# 本地核心工具白名单模块
CORE_TOOL_MODULES = [
    "tools.file_tools",
    "tools.patch_tool",
    "tools.search_tools",
    "tools.shell_tool",
]

def _load_core_native_tools():
    """仅显式加载本地核心代码沙箱工具"""
    for mod in CORE_TOOL_MODULES:
        try:
            importlib.import_module(mod)
        except Exception as e:
            print(f"[Warning] 加载核心工具模块 '{mod}' 失败: {e}")

_load_core_native_tools()

registry = default_registry

__all__ = ["registry", "register_tool"]
