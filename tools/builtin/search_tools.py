# -*- coding: utf-8 -*-
"""
tools/builtin/search_tools.py: 高性能代码搜索工具
集成本地终端深度优化：
1. 动态工作区感知 (WorkspaceContext)；
2. 优先调用本机原生 git grep / git ls-files（毫秒级、天然遵守 .gitignore）；
3. 降级为 Python 实现时自动加载解析 .gitignore 与通用构建缓存黑名单；
4. 二进制文件与敏感凭证防护；
5. 双重熔断防止上下文 Token 溢出。
"""
import os
import fnmatch
import subprocess
from pathlib import Path
from typing import List, Optional
from tools.registry import register_tool
from tools.framework.workspace import default_workspace, is_binary_file
from tools.framework.output_clamp import clamp_search_output

# 敏感与需要忽略的目录及文件黑名单（覆盖通用前端、Python、Rust 与构建产物）
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
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    "coverage",
    ".pytest_cache",
    ".tox",
    ".super-harnes",
}

# 限制上限，防止大模型 Token 爆满
MAX_SEARCH_RESULTS = 150
MAX_OUTPUT_CHARS = 12000
MAX_LINE_LENGTH = 300

def __getattr__(name: str):
    """向后兼容对 WORKSPACE_ROOT 的访问"""
    if name == "WORKSPACE_ROOT":
        return default_workspace.root
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

def _validate_search_dir(directory: str = ".") -> Path:
    """校验搜索起始目录是否在沙箱工作区内"""
    root = default_workspace.root
    target = Path(directory)
    if not target.is_absolute():
        resolved = (root / target).resolve()
    else:
        resolved = target.resolve()

    try:
        resolved.relative_to(root)
    except ValueError:
        raise PermissionError(
            f"【安全拦截】：搜索路径越界！路径 '{directory}' 超出工作区范围 ({root})。"
        )

    for part in resolved.parts:
        if part in IGNORE_PATTERNS:
            raise PermissionError(
                f"【安全拦截】：目标目录包含受保护或忽略名单 '{part}'，禁止搜索！"
            )

    return resolved

def _is_binary_file(file_path: Path) -> bool:
    """快速探测是否为二进制文件（检测前 1024 字节是否存在空字符）"""
    return is_binary_file(file_path)

def _is_git_repo(directory: Path) -> bool:
    """探测指定目录是否处于 Git 仓库中"""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(directory),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        return res.returncode == 0 and "true" in res.stdout.strip().lower()
    except Exception:
        return False

def _load_gitignore_patterns(root: Path) -> List[str]:
    """读取并解析根目录下 .gitignore 过滤规则"""
    patterns = []
    gitignore = root / ".gitignore"
    if gitignore.exists() and gitignore.is_file():
        try:
            with open(gitignore, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)
        except Exception:
            pass
    return patterns

def _is_ignored(rel_path_str: str, gitignore_patterns: List[str]) -> bool:
    """校验路径是否命中 .gitignore 或默认忽略目录"""
    parts = rel_path_str.replace("\\", "/").split("/")
    for part in parts:
        if part in IGNORE_PATTERNS or part.startswith(".env"):
            return True

    clean_rel = rel_path_str.replace("\\", "/").lstrip("./")
    for pat in gitignore_patterns:
        clean_pat = pat.rstrip("/")
        if fnmatch.fnmatch(clean_rel, clean_pat) or fnmatch.fnmatch(clean_rel, f"*{clean_pat}*"):
            return True
        for part in parts:
            if fnmatch.fnmatch(part, clean_pat):
                return True
    return False

@register_tool(
    name="find_by_name",
    is_read_only=True,
    description="""按文件名或目录名通配符（如 '*.py'、'*test*'、'agent.py'）在工作区内快速检索文件与目录。优先借助 git ls-files 毫秒级检索并自动遵守 .gitignore。
【场景指南】：专用于定位未知文件路径。若已知具体文件相对路径，请直接调用 read_file 查看；若需搜索文件内容而非文件名，请改用 grep_text。""",
    param_descriptions={
        "pattern": "文件名或路径通配符匹配规则，例如 '*.py'、'*.json'、'*test*' 或 'tools/*'",
        "directory": "搜索起始相对目录，默认为 '.'（即项目根目录）"
    }
)
def find_by_name(pattern: str, directory: str = ".") -> str:
    """
    按文件名模式搜索文件与目录：
    1. 优先尝试 git ls-files 极速检索，自动忽略 .gitignore；
    2. 降级为 Python os.walk 递归，自动解析 .gitignore 与 IGNORE_PATTERNS；
    3. 结果条数受限保护，避免 Token 溢出。
    """
    try:
        start_dir = _validate_search_dir(directory)
        if not start_dir.exists():
            return f"搜索失败：目录 '{directory}' 不存在。"
        if not start_dir.is_dir():
            return f"搜索失败：路径 '{directory}' 不是一个目录。"

        matched_items = []
        is_truncated = False
        root = default_workspace.root

        # 优先加速策略：若为 git 仓库，通过 git ls-files 毫秒级检索未忽略文件
        if _is_git_repo(start_dir):
            try:
                proc = subprocess.run(
                    ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                    cwd=str(start_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10
                )
                if proc.returncode == 0:
                    lines = proc.stdout.splitlines()
                    seen_dirs = set()
                    clean_pat = pattern.rstrip("/")

                    # 先匹配可能命中的父级目录（保证 find_by_name("tools/*") 或 find_by_name("builtin") 能检索到目录）
                    for line in lines:
                        line_clean = line.strip().replace("\\", "/")
                        if not line_clean:
                            continue
                        if any(part in IGNORE_PATTERNS for part in line_clean.split("/")):
                            continue
                        parent = Path(line_clean).parent
                        while parent and str(parent) not in (".", "/"):
                            parent_str = parent.as_posix()
                            if parent_str not in seen_dirs:
                                seen_dirs.add(parent_str)
                                parent_abs = (start_dir / parent_str).resolve()
                                try:
                                    rel_dir = parent_abs.relative_to(root).as_posix()
                                except ValueError:
                                    rel_dir = parent_str
                                dirname = parent.name
                                if (
                                    fnmatch.fnmatch(dirname.lower(), clean_pat.lower())
                                    or fnmatch.fnmatch(rel_dir.lower(), clean_pat.lower())
                                    or fnmatch.fnmatch(f"{rel_dir}/".lower(), pattern.lower())
                                ):
                                    matched_items.append(f"{rel_dir}/")
                                    if len(matched_items) >= MAX_SEARCH_RESULTS:
                                        is_truncated = True
                                        break
                            parent = parent.parent
                        if is_truncated:
                            break

                    if not is_truncated:
                        for line in lines:
                            line_clean = line.strip().replace("\\", "/")
                            if not line_clean:
                                continue
                            # 排除敏感文件
                            if any(part in IGNORE_PATTERNS for part in line_clean.split("/")):
                                continue
                            if line_clean.startswith(".env") or "id_rsa" in line_clean:
                                continue

                            # 计算完整相对路径
                            item_abs = (start_dir / line_clean).resolve()
                            try:
                                rel_to_ws = item_abs.relative_to(root).as_posix()
                            except ValueError:
                                rel_to_ws = line_clean

                            filename = Path(line_clean).name
                            if fnmatch.fnmatch(filename.lower(), pattern.lower()) or fnmatch.fnmatch(rel_to_ws.lower(), pattern.lower()):
                                matched_items.append(rel_to_ws)
                                if len(matched_items) >= MAX_SEARCH_RESULTS:
                                    is_truncated = True
                                    break

                    if matched_items:
                        matched_items.sort()
                        result_text = f"找到 {len(matched_items)} 个匹配项（模式: '{pattern}'）：\n" + "\n".join(matched_items)
                        if is_truncated:
                            result_text += f"\n\n[提示: 匹配结果超过 {MAX_SEARCH_RESULTS} 条，已截断显示]"
                        return result_text
            except Exception:
                pass  # 异常时平滑降级

        # 降级策略：Python os.walk 遍历，动态遵循 .gitignore
        gitignore_patterns = _load_gitignore_patterns(root)
        for dirpath, dirs, files in os.walk(start_dir):
            current_path = Path(dirpath)
            try:
                rel_dir = current_path.relative_to(root).as_posix()
            except ValueError:
                rel_dir = dirpath

            # 剪枝目录
            dirs[:] = [
                d for d in dirs
                if not _is_ignored(f"{rel_dir}/{d}", gitignore_patterns) and not d.startswith(".")
            ]

            # 匹配文件夹名
            for d in dirs:
                if fnmatch.fnmatch(d.lower(), pattern.lower()):
                    item_path = current_path / d
                    try:
                        rel_path = item_path.relative_to(root).as_posix()
                        matched_items.append(f"{rel_path}/")
                    except ValueError:
                        pass

            # 匹配文件名
            for f in files:
                rel_file = f"{rel_dir}/{f}"
                if _is_ignored(rel_file, gitignore_patterns):
                    continue

                if fnmatch.fnmatch(f.lower(), pattern.lower()):
                    item_path = current_path / f
                    try:
                        rel_path = item_path.relative_to(root).as_posix()
                        matched_items.append(rel_path)
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
    is_read_only=True,
    description="""在工作区代码文件中快速搜索包含指定关键字的代码行及行号。原生优先调用 git grep，毫秒级响应并自动忽略构建产物与第三方包。
【场景指南】：专用于定位变量、函数定义、类名或报错文本在哪些源码中出现。
【反向约束】：若已知确切文件行号，请直接使用 read_file；若匹配结果过多，请通过 directory 指定子目录或使用 file_pattern 过滤。""",
    param_descriptions={
        "keyword": "要在代码中检索的关键字、函数名或文本片段",
        "file_pattern": "限定搜索的文件名模式，默认为 '*'（检索所有代码文件），例如 '*.py' 或 '*.json'",
        "directory": "搜索起始相对目录，默认为 '.'（即项目根目录）"
    }
)
def grep_text(keyword: str, file_pattern: str = "*", directory: str = ".") -> str:
    """
    在指定目录的代码文件中搜索文本内容：
    1. 优先调用原生 git grep（极速检索且自动忽略 .gitignore）；
    2. 若非 git 仓库或失败，降级为 Python 实现；
    3. 过滤二进制与敏感凭据文件；
    4. 熔断防护防止撑爆上下文。
    """
    try:
        if not keyword:
            return "搜索失败：keyword 不能为空。"

        start_dir = _validate_search_dir(directory)
        if not start_dir.exists():
            return f"搜索失败：目录 '{directory}' 不存在。"
        if not start_dir.is_dir():
            return f"搜索失败：路径 '{directory}' 不是一个目录。"

        root = default_workspace.root
        matches = []
        total_chars = 0
        is_truncated = False

        # 优先加速策略：原生 git grep
        if _is_git_repo(start_dir):
            try:
                cmd = ["git", "grep", "--untracked", "-I", "-i", "-n", "-e", keyword]
                if file_pattern and file_pattern != "*":
                    cmd.extend(["--", file_pattern])

                proc = subprocess.run(
                    cmd,
                    cwd=str(start_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10
                )

                if proc.returncode == 0:
                    for line in proc.stdout.splitlines():
                        if not line.strip():
                            continue
                        parts = line.split(":", 2)
                        if len(parts) >= 3:
                            f_path, l_no, l_content = parts[0], parts[1], parts[2]
                            item_abs = (start_dir / f_path).resolve()
                            try:
                                rel_path = item_abs.relative_to(root).as_posix()
                            except ValueError:
                                rel_path = f_path

                            # 敏感文件二次防御
                            if any(p in IGNORE_PATTERNS for p in rel_path.split("/")):
                                continue
                            if rel_path.startswith(".env") or "id_rsa" in rel_path:
                                continue

                            if len(l_content) > MAX_LINE_LENGTH:
                                l_content = l_content[:MAX_LINE_LENGTH] + "... [行内容已截断]"

                            formatted_match = f"{rel_path}:{l_no}: {l_content}"
                            matches.append(formatted_match)
                            total_chars += len(formatted_match)

                            if len(matches) >= MAX_SEARCH_RESULTS or total_chars >= MAX_OUTPUT_CHARS:
                                is_truncated = True
                                break

                    if matches:
                        raw_result = f"找到 {len(matches)} 处匹配（关键字: '{keyword}', 文件模式: '{file_pattern}'）：\n" + "\n".join(matches)
                        return clamp_search_output(
                            raw_result,
                            matches=matches,
                            max_chars=MAX_OUTPUT_CHARS,
                            keyword=keyword,
                            file_pattern=file_pattern
                        )
                elif proc.returncode == 1:
                    # git grep 返回 1 表示未找到任何匹配
                    return f"未在符合 '{file_pattern}' 的文件中找到包含关键字 '{keyword}' 的内容。"
            except Exception:
                pass  # 发生非预期错误时平滑降级至 Python 实现

        # 降级策略：Python 遍历扫描
        gitignore_patterns = _load_gitignore_patterns(root)
        keyword_lower = keyword.lower()

        for dirpath, dirs, files in os.walk(start_dir):
            current_path = Path(dirpath)
            try:
                rel_dir = current_path.relative_to(root).as_posix()
            except ValueError:
                rel_dir = dirpath

            dirs[:] = [
                d for d in dirs
                if not _is_ignored(f"{rel_dir}/{d}", gitignore_patterns) and not d.startswith(".")
            ]

            for f in files:
                rel_file = f"{rel_dir}/{f}"
                if _is_ignored(rel_file, gitignore_patterns):
                    continue

                if not fnmatch.fnmatch(f.lower(), file_pattern.lower()):
                    continue

                file_path = current_path / f
                if _is_binary_file(file_path):
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as fp:
                        for line_no, line in enumerate(fp, start=1):
                            if keyword_lower in line.lower():
                                stripped_line = line.strip("\r\n")
                                if len(stripped_line) > MAX_LINE_LENGTH:
                                    stripped_line = stripped_line[:MAX_LINE_LENGTH] + "... [行内容已截断]"

                                formatted_match = f"{rel_file}:{line_no}: {stripped_line}"
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

        raw_result = f"找到 {len(matches)} 处匹配（关键字: '{keyword}', 文件模式: '{file_pattern}'）：\n" + "\n".join(matches)
        return clamp_search_output(
            raw_result,
            matches=matches,
            max_chars=MAX_OUTPUT_CHARS,
            keyword=keyword,
            file_pattern=file_pattern
        )

    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"文本搜索失败: {type(e).__name__}: {str(e)}"

