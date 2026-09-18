# -*- coding: utf-8 -*-
import os
from tools.registry import register_tool

@register_tool(
    name="list_files",
    description="列出指定目录下的所有文件和文件夹名称。默认为当前工作目录。",
    param_descriptions={"directory": "要查看的目标文件夹路径，默认为当前目录 '.'"}
)
def list_files(directory: str = ".") -> str:
    """读取指定目录下的文件列表"""
    try:
        items = os.listdir(directory)
        return "\n".join(items) if items else "目录为空"
    except Exception as e:
        return f"读取目录失败: {str(e)}"
