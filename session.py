# -*- coding: utf-8 -*-
"""
session.py: 兼容过渡层，将底层上下文管理委托给统一的 context 模块。
"""
from context.manager import ContextManager, WorkingMemory, WatermarkZone
from context.window import TurnChunk

# 别名 Session 即为 ContextManager
Session = ContextManager

__all__ = ["Session", "ContextManager", "WorkingMemory", "WatermarkZone", "TurnChunk"]
