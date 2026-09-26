# -*- coding: utf-8 -*-
import os
import re
import ast
from pathlib import Path
from typing import Optional
from tools.registry import register_tool
from tools.framework.workspace import default_workspace, atomic_write_text, is_binary_file, detect_file_encoding
from context.snapshot import default_snapshot_manager

# 敏感文件/目录黑名单：即便在工作区内，也严格禁止 Agent 读取
SENSITIVE_PATTERNS = {
    ".env",
    ".env.local",
    "id_rsa",
    "id_ed25519",
    ".git",
    "__pycache__",
}

# 单次读取的最大行数和最大字符上限
MAX_READ_LINES = 1000
MAX_READ_CHARS = 40000

AGENT_SOURCE_ROOT = Path(__file__).resolve().parents[2]

# 核心自身安全防护名单
CORE_PROTECTED_FILES = {
    "tools/file_tools.py",
    "tools/builtin/file_tools.py",
    "tools/patch_tool.py",
    "tools/builtin/patch_tool.py",
    "tools/registry.py",
    "tools/executor.py",
}

def __getattr__(name: str):
    """向后兼容对 WORKSPACE_ROOT 的访问"""
    if name == "WORKSPACE_ROOT":
        return default_workspace.root
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

def _validate_safe_path(target_path_str: str) -> Path:
    """
    核心安全边界校验器：
    1. 解析并规范化绝对路径；
    2. 校验目标路径是否严格限制在当前动态工作区范围以内；
    3. 校验文件名和路径层级是否命中敏感黑名单。
    """
    target = Path(target_path_str)
    root = default_workspace.root
    if not target.is_absolute():
        resolved = (root / target).resolve()
    else:
        resolved = target.resolve()

    # 安全检查 1：沙箱隔离校验
    try:
        resolved.relative_to(root)
    except ValueError:
        raise PermissionError(
            f"【安全拦截】：访问路径越界！路径 '{target_path_str}' 超出了允许的安全工作区范围 ({root})。"
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
    is_read_only=True,
    description="""安全读取工作区内的指定文本文件。支持按行范围分页读取，防止大文件溢出。
【反向约束与最佳实践】：面对超过 150 行的未知代码文件，严禁盲目直接从第 1 行读取全文！必须先调用 view_file_outline 提取类与函数大纲及行号，再通过 start_line/max_lines 定向切片读取。
禁止访问工作区外部路径及 .env 等敏感文件。""",
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

        if is_binary_file(safe_path):
            return f"【读取拒绝】：目标文件 '{file_path}' 为二进制文件（如图片、编译产物或数据库），无法以纯文本形式读取。"

        start_line = max(1, int(start_line))
        max_lines = min(MAX_READ_LINES, max(1, int(max_lines)))

        lines_output = []
        total_chars = 0
        is_truncated = False

        encoding = detect_file_encoding(safe_path)
        with open(safe_path, "r", encoding=encoding, errors="replace") as f:
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
    is_read_only=True,
    description="安全列出指定工作区目录下的文件和子文件夹名称。默认查看当前工作区根目录。",
    param_descriptions={"directory": "要查看的目录路径，默认为空或 '.' 表示工作区根目录"}
)
def list_files(directory: str = ".") -> str:
    """安全列出目录内容"""
    try:
        safe_path = _validate_safe_path(directory)

        if not safe_path.exists():
            return f"列出文件失败: 目录 '{directory}' 不存在。"
        if not safe_path.is_dir():
            return f"列出文件失败: '{directory}' 是文件而不是目录。"

        entries = sorted(safe_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        items = []
        for entry in entries:
            if entry.name in SENSITIVE_PATTERNS or entry.name.startswith("."):
                continue
            icon = "📄 " if entry.is_file() else "📁 "
            size_info = ""
            if entry.is_file():
                try:
                    size_kb = entry.stat().st_size / 1024
                    size_info = f" ({size_kb:.1f} KB)"
                except Exception:
                    pass
            items.append(f"{icon}{entry.name}{size_info}")

        if not items:
            return f"目录 '{directory}' 为空或仅包含隐藏敏感文件。"

        header = f"【目录内容清单】 `{directory}` (共 {len(items)} 项):\n"
        return header + "\n".join(items)

    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"列出文件失败: {type(e).__name__}: {str(e)}"

@register_tool(
    name="view_file_outline",
    is_read_only=True,
    description="快速提取指定代码文件的顶层符号骨架（类、函数、方法、行号与文档注释），不返回函数具体实现体。极其节省上下文 Tokens，适用于全局架构理解。",
    param_descriptions={
        "file_path": "工作区内的代码文件相对路径，如 'core/agent.py' 或 'context/manager.py'"
    }
)
def view_file_outline(file_path: str) -> str:
    """基于 AST 与正则的极速代码骨架大纲提取器"""
    try:
        safe_path = _validate_safe_path(file_path)

        if not safe_path.exists():
            return f"查看大纲失败: 文件 '{file_path}' 不存在。"
        if not safe_path.is_file():
            return f"查看大纲失败: '{file_path}' 是目录而不是文件。"

        if is_binary_file(safe_path):
            return f"【查看大纲拒绝】：目标文件 '{file_path}' 为二进制文件，无法提取代码骨架。"

        encoding = detect_file_encoding(safe_path)
        with open(safe_path, "r", encoding=encoding, errors="replace") as f:
            content = f.read()

        total_lines = len(content.splitlines())

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

        # 通用大纲提取
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

def _check_python_syntax(file_path: Path, content: str) -> str:
    """对 Python 文件做 AST 语法即时自检"""
    if file_path.suffix == ".py":
        try:
            ast.parse(content, filename=file_path.name)
        except SyntaxError as se:
            return (
                f"\n【写入警告】：文件已写入，但检测到 Python 语法错误 "
                f"(SyntaxError: line {se.lineno}: {se.msg})，请立即修复！"
            )
    return ""

@register_tool(
    name="write_file",
    description="""专用于全新创建文件或大面积重写文件。
【反向约束与选型互斥】：严禁为了微调几行现有代码而调用此工具整盘覆写！修改现有文件请优先使用最小侵入性的 apply_patch 工具；仅当全新创建文件或 apply_patch 因冲突无法解决时才使用此工具。禁止覆盖核心安全模块。""",
    param_descriptions={
        "file_path": "工作区内的目标文件路径，例如 'tools/helper.py'",
        "content": "写入文件的完整文本内容"
    }
)
def write_file(file_path: str, content: str) -> str:
    """安全覆盖写入或创建文件，写前自动触发物理磁盘快照"""
    try:
        safe_path = _validate_safe_path(file_path)
        root = default_workspace.root
        try:
            norm_rel = safe_path.relative_to(root).as_posix()
        except ValueError:
            return f"【安全拦截】：目标路径 '{file_path}' 越出工作区范围，禁止写入！"

        if default_workspace.root == AGENT_SOURCE_ROOT and norm_rel in CORE_PROTECTED_FILES:
            return f"【安全拦截】：'{norm_rel}' 属于 Agent 核心安全引擎文件，已被设为只读保护，禁止写入！"

        # 核心增强：写前自动创建物理磁盘快照，支持真正的 /undo 物理还原
        default_snapshot_manager.backup_before_mutation(safe_path)

        atomic_write_text(safe_path, content, encoding="utf-8")

        syntax_warning = _check_python_syntax(safe_path, content)
        return f"【写入成功】文件 '{file_path}' 已成功写入（共 {len(content)} 字符）。{syntax_warning}"
    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"写入文件失败: {type(e).__name__}: {str(e)}"


__all__ = [
    "read_file",
    "list_files",
    "view_file_outline",
    "write_file",
    "atomic_write_text",
    "is_binary_file",
]
