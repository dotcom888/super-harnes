# -*- coding: utf-8 -*-
import os
from pathlib import Path
from typing import Optional
from tools.registry import register_tool

# 定义当前允许访问的安全根工作区（默认为项目根目录）
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

# 敏感文件/目录黑名单：即便在工作区内，也严格禁止 Agent 读取
SENSITIVE_PATTERNS = {
    ".env",
    ".env.local",
    "id_rsa",
    "id_ed25519",
    ".git",
    "__pycache__",
}

# 单次读取的最大行数和最大字符上限，防止超大文件导致大模型上下文（Token）爆满
MAX_READ_LINES = 300
MAX_READ_CHARS = 15000

def _validate_safe_path(target_path_str: str) -> Path:
    """
    核心安全边界校验器：
    1. 解析并规范化绝对路径（消除 ../ 穿越符号和软链接风险）；
    2. 校验目标路径是否严格限制在 WORKSPACE_ROOT 沙箱范围以内；
    3. 校验文件名和路径层级是否命中敏感黑名单。
    """
    target = Path(target_path_str)
    if not target.is_absolute():
        resolved = (WORKSPACE_ROOT / target).resolve()
    else:
        resolved = target.resolve()

    # 安全检查 1：沙箱隔离校验（防止跨盘符、防止 ../ 跳出工作区）
    try:
        resolved.relative_to(WORKSPACE_ROOT)
    except ValueError:
        raise PermissionError(
            f"【安全拦截】：访问路径越界！路径 '{target_path_str}' 超出了允许的安全工作区范围 ({WORKSPACE_ROOT})。"
        )

    # 安全检查 2：敏感文件黑名单拦截
    for part in resolved.parts:
        if part in SENSITIVE_PATTERNS:
            raise PermissionError(
                f"【安全拦截】：禁止读取敏感文件或受保护目录 '{part}'！"
            )

    return resolved

@register_tool(
    name="read_file",
    description="安全读取工作区内的指定文本文件。支持按行范围分页读取，防止大文件溢出。禁止访问工作区外部路径及 .env 等敏感文件。",
    param_descriptions={
        "file_path": "工作区内的相对或绝对文件路径，例如 'requirements.txt' 或 'tools/calculator.py'",
        "start_line": "起始行号（从 1 开始计，默认为 1）",
        "max_lines": f"单次最多读取行数（默认为 100 行，上限不超过 {MAX_READ_LINES} 行）"
    }
)
def read_file(file_path: str, start_line: int = 1, max_lines: int = 100) -> str:
    """带四重安全防线的文件读取工具"""
    try:
        safe_path = _validate_safe_path(file_path)

        if not safe_path.exists():
            return f"读取失败: 文件 '{file_path}' 不存在。"
        if not safe_path.is_file():
            return f"读取失败: 目标路径 '{file_path}' 是文件夹而不是文件。"

        start_line = max(1, int(start_line))
        max_lines = min(MAX_READ_LINES, max(1, int(max_lines)))

        lines_output = []
        total_chars = 0
        is_truncated = False

        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f, start=1):
                if idx < start_line:
                    continue
                if len(lines_output) >= max_lines:
                    is_truncated = True
                    break

                if total_chars + len(line) > MAX_READ_CHARS:
                    lines_output.append(f"--- [提示: 达到单次字符上限 {MAX_READ_CHARS}，已自动截断] ---")
                    is_truncated = True
                    break

                # 兼容 Python 3.11 及以下版本：避免在 f-string 花括号内使用反斜杠 \r\n
                stripped_line = line.rstrip("\r\n")
                lines_output.append(f"{idx:4d} | {stripped_line}")
                total_chars += len(line)

        if not lines_output:
            return f"文件 '{file_path}' 从第 {start_line} 行开始无内容（已到达文件末尾或为空文件）。"

        result_text = "\n".join(lines_output)
        if is_truncated:
            result_text += f"\n\n[提示: 当前文件未完全读完，若需后续内容，可指定 start_line={start_line + len(lines_output)} 继续分段读取]"

        return result_text

    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"读取文件时发生意外错误: {type(e).__name__}: {str(e)}"

@register_tool(
    name="list_files",
    description="安全列出指定工作区目录下的文件和子文件夹名称。默认查看当前工作区根目录。",
    param_descriptions={"directory": "要查看的目录路径，默认为空或 '.' 表示工作区根目录"}
)
def list_files(directory: str = ".") -> str:
    """安全列出目录内容"""
    try:
        safe_path = _validate_safe_path(directory)

        if not safe_path.exists():
            return f"目录不存在: '{directory}'"
        if not safe_path.is_dir():
            return f"路径 '{directory}' 不是文件夹"

        items = []
        for entry in safe_path.iterdir():
            if entry.name in SENSITIVE_PATTERNS:
                continue
            suffix = "/" if entry.is_dir() else ""
            items.append(f"{entry.name}{suffix}")

        return "\n".join(sorted(items)) if items else "（目录为空）"
    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"列出目录失败: {type(e).__name__}: {str(e)}"
