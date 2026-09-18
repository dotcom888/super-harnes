# -*- coding: utf-8 -*-
import importlib
import pkgutil
from pathlib import Path
from tools.registry import default_registry, register_tool

def _auto_discover_tools():
    """
    自动扫描并加载当前 tools/ 目录下的所有 Python 模块。
    任何新增的 .py 工具文件只需放入本目录，都会被自动引入并触发 @register_tool。
    """
    current_dir = Path(__file__).parent
    for module_info in pkgutil.iter_modules([str(current_dir)]):
        mod_name = module_info.name
        # 排除注册中心本身和当前初始化脚本
        if mod_name not in ("registry", "__init__"):
            importlib.import_module(f"tools.{mod_name}")

# 执行自动发现
_auto_discover_tools()

# 对外统一暴露单例 registry 和装饰器
registry = default_registry

__all__ = ["registry", "register_tool"]
