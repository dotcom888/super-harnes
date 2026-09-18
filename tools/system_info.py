# -*- coding: utf-8 -*-
import datetime
import platform
from tools.registry import register_tool

@register_tool(
    name="get_current_time",
    description="获取当前操作系统的精确日期和时间。当用户询问现在几点、今天周几或当前具体日期时调用此工具。"
)
def get_current_time() -> str:
    """获取当前系统时间"""
    now = datetime.datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekdays[now.weekday()]
    return f"当前时间为: {now.strftime('%Y-%m-%d %H:%M:%S')} ({weekday})"

@register_tool(
    name="get_system_info",
    description="获取当前运行环境的操作系统类型、版本及 Python 版本信息。"
)
def get_system_info() -> str:
    """获取系统与环境概要信息"""
    return (
        f"操作系统: {platform.system()} {platform.release()} ({platform.version()})\n"
        f"架构: {platform.machine()}\n"
        f"Python 版本: {platform.python_version()}"
    )
