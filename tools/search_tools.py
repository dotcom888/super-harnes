# -*- coding: utf-8 -*-
import os
import fnmatch
from pathlib import Path
from typing import List, Optional
from tools.registry import register_tool

# 当前工作区根目录
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# 敏感与需要忽略的目录及文件黑名单（避免遍历第三方包或敏感信息导致性能与安全问题）
IGNORE_PATTERNS = {
    ".env",
    ".env.local",
    "id_rsa",
    "id_ed25519",
    ".git",
    ".venv",
    "__pycache__",
    ".idea",
    ".vscode",
    "node_modules",
}

# 限制上限，防止大模型 Token 爆满
MAX_SEARCH_RESULTS = 100
MAX_OUTPUT_CHARS = 12000
MAX_LINE_LENGTH = 300

def _validate_search_dir(directory: str = ".") -> Path:
    """校验搜索起始目录是否在沙箱工作区内"""
    target = Path(directory)
    if not target.is_absolute():
        resolved = (WORKSPACE_ROOT / target).resolve()
    else:
        resolved = target.resolve()

    try:
        resolved.relative_to(WORKSPACE_ROOT)
    except ValueError:
        raise PermissionError(
            f"【安全拦截】：搜索路径越界！路径 '{directory}' 超出工作区范围 ({WORKSPACE_ROOT})。"
        )

    for part in resolved.parts:
        if part in IGNORE_PATTERNS:
            raise PermissionError(
                f"【安全拦截】：目标目录包含受保护或忽略名单 '{part}'，禁止搜索！"
            )

    return resolved

def _is_binary_file(file_path: Path) -> bool:
    """快速探测是否为二进制文件（检测前 1024 字节是否存在空字符）"""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\x00" in chunk
    except Exception:
        return True

@register_tool(
    name="find_by_name",
    description="按文件名通配符（如 '*.py'、'*test*'、'agent.py'）在工作区内快速检索文件与目录。自动过滤 .venv、.git、.env 等目录及敏感文件。",
    param_descriptions={
        "pattern": "文件名或路径通配符匹配规则，例如 '*.py'、'*.json'、'*test*' 或 'tools/*'",
        "directory": "搜索起始相对目录，默认为 '.'（即项目根目录）"
    }
)
def find_by_name(pattern: str, directory: str = ".") -> str:
    """
    按文件名模式递归搜索文件与目录：
    1. 自动过滤 .venv、.git、__pycache__ 等非业务目录；
    2. 支持通配符匹配（大小写不敏感）；
    3. 输出相对路径并标明目录/文件；
    4. 结果条数受限保护，避免 Token 溢出。
    """
    try:
        start_dir = _validate_search_dir(directory)
        if not start_dir.exists():
            return f"搜索失败：目录 '{directory}' 不存在。"
        if not start_dir.is_dir():
            return f"搜索失败：路径 '{directory}' 不是一个目录。"

        matched_items = []
        is_truncated = False

        for root, dirs, files in os.walk(start_dir):
            # 原地修改 dirs 以跳过忽略目录，避免深入遍历
            dirs[:] = [d for d in dirs if d not in IGNORE_PATTERNS and not d.startswith(".")]

            current_root = Path(root)

            # 匹配文件夹
            for d in dirs:
                if fnmatch.fnmatch(d.lower(), pattern.lower()):
                    item_path = current_root / d
                    try:
                        rel_path = item_path.relative_to(WORKSPACE_ROOT)
                        matched_items.append(f"{rel_path.as_posix()}/")
                    except ValueError:
                        pass

            # 匹配文件
            for f in files:
                if f in IGNORE_PATTERNS or f.startswith(".env"):
                    continue
                if fnmatch.fnmatch(f.lower(), pattern.lower()):
                    item_path = current_root / f
                    try:
                        rel_path = item_path.relative_to(WORKSPACE_ROOT)
                        matched_items.append(rel_path.as_posix())
                    except ValueError:
                        pass

                if len(matched_items) >= MAX_SEARCH_RESULTS:
                    is_truncated = True
                    break

            if is_truncated:
                break

        if not matched_items:
            return f"未找到匹配模式 '{pattern}' 的文件或目录。"

        matched_items.sort()
        result_text = f"找到 {len(matched_items)} 个匹配项（模式: '{pattern}'）：\n" + "\n".join(matched_items)
        if is_truncated:
            result_text += f"\n\n[提示: 匹配结果超过 {MAX_SEARCH_RESULTS} 条，已截断显示]"

        return result_text

    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"搜索文件失败: {type(e).__name__}: {str(e)}"

@register_tool(
    name="grep_text",
    description="在工作区代码文件中快速搜索包含指定关键字或函数名的代码行及行号。支持按文件类型过滤（如 '*.py'）。自动过滤 .venv、.git、.env 及二进制文件。",
    param_descriptions={
        "keyword": "要在代码中检索的关键字、函数名或文本片段",
        "file_pattern": "限定搜索的文件名模式，默认为 '*'（检索所有文本代码文件），例如 '*.py' 或 '*.json'",
        "directory": "搜索起始相对目录，默认为 '.'（即项目根目录）"
    }
)
def grep_text(keyword: str, file_pattern: str = "*", directory: str = ".") -> str:
    """
    在指定目录的代码文件中搜索指定文本内容：
    1. 自动跳过 .venv、.git 等虚拟环境与缓存目录；
    2. 自动过滤二进制与敏感文件；
    3. 支持按文件名过滤；
    4. 输出格式为 '文件路径:行号: 代码内容'，超长行自动折叠；
    5. 具备总字符数与命中条数双重安全熔断。
    """
    try:
        if not keyword:
            return "搜索失败：keyword 不能为空。"

        start_dir = _validate_search_dir(directory)
        if not start_dir.exists():
            return f"搜索失败：目录 '{directory}' 不存在。"
        if not start_dir.is_dir():
            return f"搜索失败：路径 '{directory}' 不是一个目录。"

        matches = []
        total_chars = 0
        is_truncated = False
        keyword_lower = keyword.lower()

        for root, dirs, files in os.walk(start_dir):
            # 剪枝跳过无关目录
            dirs[:] = [d for d in dirs if d not in IGNORE_PATTERNS and not d.startswith(".")]

            current_root = Path(root)

            for f in files:
                if f in IGNORE_PATTERNS or f.startswith(".env"):
                    continue

                if not fnmatch.fnmatch(f.lower(), file_pattern.lower()):
                    continue

                file_path = current_root / f
                if _is_binary_file(file_path):
                    continue

                try:
                    rel_path = file_path.relative_to(WORKSPACE_ROOT).as_posix()
                except ValueError:
                    rel_path = str(file_path)

                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as fp:
                        for line_no, line in enumerate(fp, start=1):
                            # 大小写不敏感匹配
                            if keyword_lower in line.lower():
                                stripped_line = line.strip("\r\n")
                                if len(stripped_line) > MAX_LINE_LENGTH:
                                    stripped_line = stripped_line[:MAX_LINE_LENGTH] + "... [行内容已截断]"

                                formatted_match = f"{rel_path}:{line_no}: {stripped_line}"
                                matches.append(formatted_match)
                                total_chars += len(formatted_match)

                                if len(matches) >= MAX_SEARCH_RESULTS or total_chars >= MAX_OUTPUT_CHARS:
                                    is_truncated = True
                                    break
                except Exception:
                    continue

                if is_truncated:
                    break

            if is_truncated:
                break

        if not matches:
            return f"未在符合 '{file_pattern}' 的文件中找到包含关键字 '{keyword}' 的内容。"

        result_text = f"找到 {len(matches)} 处匹配（关键字: '{keyword}', 文件模式: '{file_pattern}'）：\n" + "\n".join(matches)
        if is_truncated:
            result_text += f"\n\n[提示: 匹配结果过多，已达到单次显示上限（最多 {MAX_SEARCH_RESULTS} 条 / {MAX_OUTPUT_CHARS} 字符）]"

        return result_text

    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"文本搜索失败: {type(e).__name__}: {str(e)}"
