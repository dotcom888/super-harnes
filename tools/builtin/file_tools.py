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

import re
import ast

# 单次读取的最大行数和最大字符上限（放宽限制以适应现代长上下文 Coding Agent）
MAX_READ_LINES = 1000
MAX_READ_CHARS = 40000

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
        "max_lines": f"单次最多读取行数（默认为 300 行，上限不超过 {MAX_READ_LINES} 行）"
    }
)
def read_file(file_path: str, start_line: int = 1, max_lines: int = 300) -> str:
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

@register_tool(
    name="view_file_outline",
    description="快速提取代码文件的大纲结构（包括类定义、函数/方法签名、参数、行号范围及文档注释）。优先在通读全文件前使用，快速定位核心模块并节约步数与 Token。",
    param_descriptions={
        "file_path": "工作区内的代码文件路径，例如 'context/manager.py' 或 'core/agent.py'"
    }
)
def view_file_outline(file_path: str) -> str:
    """提取代码文件大纲（支持 Python AST 与通用代码正则解析）"""
    try:
        safe_path = _validate_safe_path(file_path)
        if not safe_path.exists():
            return f"查看大纲失败: 文件 '{file_path}' 不存在。"
        if not safe_path.is_file():
            return f"查看大纲失败: 路径 '{file_path}' 是文件夹。"

        content = safe_path.read_text(encoding="utf-8", errors="replace")
        total_lines = len(content.splitlines())

        # 如果是 Python 文件，使用 ast 解析高精度大纲
        if safe_path.suffix == ".py":
            try:
                tree = ast.parse(content, filename=str(safe_path))
                outline = [f"【Python 文件代码大纲】 `{file_path}` (全文件共 {total_lines} 行):"]
                
                doc = ast.get_docstring(tree)
                if doc:
                    first_line = doc.strip().splitlines()[0]
                    outline.append(f"  • 模块说明: {first_line[:80]}")

                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        c_doc = ast.get_docstring(node)
                        c_desc = f" - {c_doc.strip().splitlines()[0][:60]}" if c_doc else ""
                        end_line = getattr(node, "end_lineno", node.lineno)
                        outline.append(f"\n📁 class {node.name} (第 {node.lineno} ~ {end_line} 行){c_desc}:")
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                args = [a.arg for a in item.args.args]
                                args_str = ", ".join(args)
                                f_doc = ast.get_docstring(item)
                                f_desc = f" -> {f_doc.strip().splitlines()[0][:50]}" if f_doc else ""
                                f_end = getattr(item, "end_lineno", item.lineno)
                                outline.append(f"   └── def {item.name}({args_str}) (第 {item.lineno} ~ {f_end} 行){f_desc}")
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = [a.arg for a in node.args.args]
                        args_str = ", ".join(args)
                        f_doc = ast.get_docstring(node)
                        f_desc = f" -> {f_doc.strip().splitlines()[0][:50]}" if f_doc else ""
                        f_end = getattr(node, "end_lineno", node.lineno)
                        outline.append(f"⚙️ def {node.name}({args_str}) (第 {node.lineno} ~ {f_end} 行){f_desc}")

                if len(outline) <= 2:
                    outline.append("  (文件中未检测到顶层类或函数定义)")
                return "\n".join(outline)
            except SyntaxError:
                pass

        # 通用文本/正则大纲提取（JS/TS/通用代码）
        outline = [f"【代码文件符号大纲】 `{file_path}` (全文件共 {total_lines} 行):"]
        pattern = re.compile(r"^\s*(class\s+\w+|def\s+\w+|function\s+\w+|const\s+\w+\s*=\s*(?:function|\()|export\s+(?:default\s+)?(?:class|function)\s+\w+)", re.MULTILINE)
        lines = content.splitlines()
        found = 0
        for idx, line in enumerate(lines, start=1):
            m = pattern.match(line)
            if m:
                found += 1
                outline.append(f"  第 {idx:4d} 行 | {line.strip()[:100]}")
                if found >= 150:
                    outline.append("  ... (大纲条目过多，仅展示前 150 项)")
                    break

        if found == 0:
            outline.append("  (未检测到明显的函数或类声明)")
        return "\n".join(outline)

    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"生成大纲失败: {type(e).__name__}: {str(e)}"


CORE_PROTECTED_FILES = {
    "tools/file_tools.py",
    "tools/builtin/file_tools.py",
    "tools/patch_tool.py",
    "tools/builtin/patch_tool.py",
    "tools/registry.py",
    "tools/executor.py",
}

@register_tool(
    name="write_file",
    description="安全创建或覆盖写入指定文件。当全新创建文件或使用 apply_patch 屡次因锚点匹配受挫时，可直接使用此工具进行文件全量写入。禁止覆盖核心安全模块。",
    param_descriptions={
        "file_path": "工作区内的目标文件路径，例如 'tools/helper.py'",
        "content": "写入文件的完整文本内容"
    }
)
def write_file(file_path: str, content: str) -> str:
    """安全覆盖写入或创建文件"""
    try:
        safe_path = _validate_safe_path(file_path)
        try:
            norm_rel = safe_path.relative_to(WORKSPACE_ROOT).as_posix()
        except ValueError:
            return f"【安全拦截】：目标路径 '{file_path}' 越出工作区范围，禁止写入！"

        if norm_rel in CORE_PROTECTED_FILES:
            return f"【安全拦截】：'{norm_rel}' 属于 Agent 核心安全引擎文件，已被设为只读保护，禁止写入！"

        safe_path.parent.mkdir(parents=True, exist_ok=True)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"【写入成功】文件 '{file_path}' 已成功写入（共 {len(content)} 字符）。"
    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"写入文件失败: {type(e).__name__}: {str(e)}"
