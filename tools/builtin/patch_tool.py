# -*- coding: utf-8 -*-
"""
tools/builtin/patch_tool.py: 增强型补丁工具
包含：
1. 全局 \r\n 预归一化；
2. 行号前缀 (如 "  42 | ") 容错智能剥离；
3. Python AST 语法即时自检诊断；
4. 控制台彩色 Unified Diff 渲染；
5. 多文件/多修改块事务原子性 (Patch Transaction) 保护；
6. 自动接入物理磁盘快照，支持无缝 /undo 磁盘还原。
"""
import re
import ast
import difflib
from pathlib import Path
from typing import List, Tuple, Optional
from tools.registry import register_tool
from tools.framework.workspace import default_workspace, atomic_write_text
from context.snapshot import default_snapshot_manager, PatchTransaction

# 敏感与保护名单：严禁写入、篡改或覆盖
FORBIDDEN_PATTERNS = {
    ".env",
    ".env.local",
    ".git",
    ".venv",
    "id_rsa",
    "id_ed25519",
    "__pycache__",
}

AGENT_SOURCE_ROOT = Path(__file__).resolve().parents[2]

# 核心自保护名单：防止大模型通过补丁篡改自身的安全沙箱模块
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

def _validate_patch_target(target_path_str: str) -> Path:
    """
    针对文件写入操作的严苛安全校验：
    1. 规范化绝对路径，杜绝 ../ 路径穿越；
    2. 沙箱校验：必须严格在当前工作区内部；
    3. 敏感凭证与环境资产保护；
    4. Agent 核心安全组件自保护。
    """
    root = default_workspace.root
    target = Path(target_path_str)
    if not target.is_absolute():
        resolved = (root / target).resolve()
    else:
        resolved = target.resolve()

    # 1. 沙箱越界校验
    try:
        relative_path = resolved.relative_to(root)
    except ValueError:
        raise PermissionError(
            f"【安全拦截】：目标路径 '{target_path_str}' 越出工作区范围，禁止写入！"
        )

    # 2. 敏感黑名单拦截
    for part in resolved.parts:
        if part in FORBIDDEN_PATTERNS:
            raise PermissionError(
                f"【安全拦截】：目标路径包含受保护资产 '{part}'，禁止写入！"
            )

    # 3. 跨工作区防篡改保护：当处于非 super-harnes 项目时，绝对禁止修改 super-harnes 自身源码
    if default_workspace.root.resolve() != AGENT_SOURCE_ROOT.resolve():
        try:
            resolved.relative_to(AGENT_SOURCE_ROOT.resolve())
            raise PermissionError(
                f"【安全隔离拦截】：当前处于独立工作区 '{default_workspace.root.name}'，禁止修改 super 智能体自身源码目录 ({AGENT_SOURCE_ROOT})！"
            )
        except ValueError:
            pass

    # 4. 核心自身源码保护（仅当操作 Agent 自身源码仓库时保护内核）
    norm_rel = relative_path.as_posix()
    if default_workspace.root == AGENT_SOURCE_ROOT and norm_rel in CORE_PROTECTED_FILES:
        raise PermissionError(
            f"【安全拦截】：'{norm_rel}' 属于 Agent 核心安全引擎文件，已被设为只读保护！"
        )

    return resolved

def _strip_line_numbers(text: str) -> str:
    """剥离大模型从 read_file 误复制的行号前缀，如 '  42 | import os' -> 'import os'"""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        cleaned.append(re.sub(r"^\s*\d+\s*\|\s?", "", line))
    return "\n".join(cleaned)

def _generate_diff(original: str, modified: str, filepath: str) -> str:
    """生成标准 unified diff"""
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff_lines = list(difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
        lineterm=""
    ))
    return "".join(diff_lines)

def _colorize_diff(diff_text: str) -> str:
    """在终端为 diff 添加 ANSI 颜色高亮（红/绿/青）"""
    colored = []
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            colored.append(f"\033[1m{line}\033[0m")
        elif line.startswith("+"):
            colored.append(f"\033[32m{line}\033[0m")
        elif line.startswith("-"):
            colored.append(f"\033[31m{line}\033[0m")
        elif line.startswith("@@"):
            colored.append(f"\033[36m{line}\033[0m")
        else:
            colored.append(line)
    return "\n".join(colored)

def _check_python_syntax(file_path: Path, content: str) -> str:
    """对 Python 文件做 AST 语法即时自检"""
    if file_path.suffix == ".py":
        try:
            ast.parse(content, filename=file_path.name)
        except SyntaxError as se:
            return (
                f"\n【补丁警告】：文件已修改，但检测到 Python 语法错误 "
                f"(SyntaxError: line {se.lineno}: {se.msg})，请立即修复！"
            )
    return ""

def _apply_create_file(file_path_str: str, content: str, tx: PatchTransaction) -> Tuple[bool, str]:
    """安全创建新文件并记录事务"""
    resolved_path = _validate_patch_target(file_path_str)
    tx.record_before_touch(resolved_path)

    atomic_write_text(resolved_path, content, encoding="utf-8")

    syntax_warning = _check_python_syntax(resolved_path, content)
    msg = f"【创建成功】文件 '{file_path_str}' 已成功创建（共 {len(content)} 字符）。{syntax_warning}"
    return True, msg

def _apply_update_blocks(
    file_path_str: str,
    blocks: List[Tuple[str, str]],
    tx: PatchTransaction
) -> Tuple[bool, str]:
    """对已有文件应用锚点替换块，支持行号容错、空白容错与 AST 语法自检"""
    resolved_path = _validate_patch_target(file_path_str)

    if not resolved_path.exists() or not resolved_path.is_file():
        return False, f"【补丁失败】目标文件 '{file_path_str}' 不存在，无法应用更新补丁。"

    # 记录事务前状态
    tx.record_before_touch(resolved_path)

    with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
        original_content = f.read()

    # 记录原文件换行符风格，Windows CRLF 原生文件保全
    is_crlf = ("\r\n" in original_content)
    modified_content = original_content

    for idx, (raw_search, raw_replace) in enumerate(blocks, start=1):
        if not raw_search:
            continue

        search_block = raw_search
        replace_block = raw_replace

        # 尝试 1：精确匹配
        occurrences = modified_content.count(search_block)
        if occurrences == 1:
            modified_content = modified_content.replace(search_block, replace_block, 1)
            continue

        # 尝试 2：换行符风格差异归一化 (\r\n 与 \n)
        norm_mod = modified_content.replace("\r\n", "\n")
        norm_search = search_block.replace("\r\n", "\n")
        if norm_mod.count(norm_search) == 1:
            norm_replace = replace_block.replace("\r\n", "\n")
            modified_content = norm_mod.replace(norm_search, norm_replace, 1)
            continue

        # 尝试 2.1：文件末尾缺少换行符 (No newline at EOF) 容错
        norm_search_rstrip = norm_search.rstrip("\n")
        norm_replace_rstrip = replace_block.replace("\r\n", "\n")
        if norm_search.endswith("\n") and not norm_mod.endswith("\n"):
            if norm_mod.endswith(norm_search_rstrip) and norm_mod.count(norm_search_rstrip) == 1:
                new_content = norm_mod[:-len(norm_search_rstrip)] + norm_replace_rstrip
                modified_content = new_content
                continue

        # 尝试 3：忽略行尾空白差异模糊匹配 (Trailing Whitespace Fuzzy Match)
        mod_lines = norm_mod.split("\n")
        search_lines = norm_search.split("\n")
        mod_lines_rstrip = [l.rstrip() for l in mod_lines]
        search_lines_rstrip = [l.rstrip() for l in search_lines]
        search_len = len(search_lines_rstrip)

        # 容错：如果原文件末尾无换行，而 search 块末尾有多余空行，尝试在 EOF 处匹配
        if (
            search_lines_rstrip
            and search_lines_rstrip[-1] == ""
            and mod_lines_rstrip
            and mod_lines_rstrip[-1] != ""
        ):
            trimmed_search = search_lines_rstrip[:-1]
            t_len = len(trimmed_search)
            if t_len > 0 and len(mod_lines_rstrip) >= t_len:
                if mod_lines_rstrip[-t_len:] == trimmed_search:
                    start_i = len(mod_lines_rstrip) - t_len
                    replace_lines = replace_block.replace("\r\n", "\n").split("\n")
                    new_lines = mod_lines[:start_i] + replace_lines
                    modified_content = "\n".join(new_lines)
                    continue

        matched_via_whitespace = False
        if search_len > 0 and len(mod_lines_rstrip) >= search_len:
            match_indices = []
            for i in range(len(mod_lines_rstrip) - search_len + 1):
                if mod_lines_rstrip[i : i + search_len] == search_lines_rstrip:
                    match_indices.append(i)

            if len(match_indices) == 1:
                start_i = match_indices[0]
                replace_lines = replace_block.replace("\r\n", "\n").split("\n")
                new_lines = mod_lines[:start_i] + replace_lines + mod_lines[start_i + search_len:]
                modified_content = "\n".join(new_lines)
                matched_via_whitespace = True
                continue
            elif len(match_indices) > 1:
                return False, (
                    f"【补丁失败】：在文件中找到了 {len(match_indices)} 处近似的 SEARCH 锚点代码（行尾空格模糊匹配），"
                    f"定位不唯一！请在 SEARCH 块中增加上下文（前后几行代码）以准确定位。"
                )

        # 尝试 4：智能剥离大模型误带的 read_file 行号前缀 (如 "  42 | ")
        stripped_search = _strip_line_numbers(norm_search)
        if stripped_search != norm_search:
            # SEARCH 块带行号前缀
            clean_replace = _strip_line_numbers(replace_block.replace("\r\n", "\n"))
            if norm_mod.count(stripped_search) == 1:
                modified_content = norm_mod.replace(stripped_search, clean_replace, 1)
                continue

            # 行号剥离 + 行尾空白模糊匹配组合
            clean_search_lines = [l.rstrip() for l in stripped_search.split("\n")]
            clean_len = len(clean_search_lines)
            if clean_len > 0 and len(mod_lines_rstrip) >= clean_len:
                match_indices = []
                for i in range(len(mod_lines_rstrip) - clean_len + 1):
                    if mod_lines_rstrip[i : i + clean_len] == clean_search_lines:
                        match_indices.append(i)

                if len(match_indices) == 1:
                    start_i = match_indices[0]
                    rep_lines = clean_replace.split("\n")
                    new_lines = mod_lines[:start_i] + rep_lines + mod_lines[start_i + clean_len:]
                    modified_content = "\n".join(new_lines)
                    continue

        if occurrences > 1:
            return False, (
                f"【补丁失败】：在文件中找到了 {occurrences} 处相同的 SEARCH 锚点代码，"
                f"定位不唯一！请在 SEARCH 块中增加上下文（前后几行代码）以准确定位。"
            )

        return False, (
            f"【补丁失败】：在文件第 {idx} 个修改块中未找到匹配的 SEARCH 锚点代码。\n"
            f"请确保 SEARCH 中的代码与原文件完全一致（包含缩进和空行）。"
        )

    # 换行符保全：如果原文件使用 Windows CRLF，统一还原为 CRLF，杜绝全库换行符突变污染
    if is_crlf:
        modified_content = modified_content.replace("\r\n", "\n").replace("\n", "\r\n")

    # 原子写入目标文件，杜绝写过程中断损坏
    atomic_write_text(resolved_path, modified_content, encoding="utf-8")

    # 语法自检
    syntax_warning = _check_python_syntax(resolved_path, modified_content)

    # 生成控制台终端 diff 展示
    diff_text = _generate_diff(original_content, modified_content, file_path_str)
    if diff_text:
        try:
            print(f"\n[Patch Diff] {file_path_str}:\n{_colorize_diff(diff_text)}")
        except Exception:
            pass

    msg = f"【补丁成功】文件 '{file_path_str}' 已成功修改，共完成 {len(blocks)} 处代码块替换。{syntax_warning}"
    return True, msg

@register_tool(
    name="apply_patch",
    description="""专用于对已有文件进行局部精准修改与代码替换（基于 SEARCH/REPLACE 锚点块）。
【反向约束与选型互斥】：本工具专用于已有代码的最小侵入式修改（具备事务原子性：任一文件失败全自动回滚；支持行号剥离与 AST 语法自检）。若全新创建空白文件，请改用 write_file 工具。
格式说明：
修改现有文件（使用精准 SEARCH/REPLACE 块）：
*** Update File: 相对路径
<<<<<<< SEARCH
要被替换的原始代码（必须与原文件中的字符、缩进完全一致）
=======
替换后的新代码
>>>>>>> REPLACE
""",
    param_descriptions={
        "patch_content": "补丁指令字符串，包含 *** Update File 块与 SEARCH/REPLACE 内容"
    }
)
def apply_patch(patch_content: str) -> str:
    """解析并应用补丁的主入口，受 PatchTransaction 原子事务保护"""
    try:
        # 1. 全局 \r\n 预归一化
        content = patch_content.replace("\r\n", "\n").strip()
        results = []

        create_pattern = re.compile(
            r"\*\*\*\s*Create File:\s*(.*?)\n(.*?)(?:\n\*\*\*\s*End File|\Z)",
            re.DOTALL
        )
        update_file_pattern = re.compile(
            r"\*\*\*\s*Update File:\s*([^\n]+)(.*?)(?=(\*\*\*\s*(?:Update|Create) File:)|\Z)",
            re.DOTALL
        )
        block_pattern = re.compile(
            r"<<<<<<<\s*SEARCH\n(.*?)=======\n(.*?)>>>>>>>\s*REPLACE",
            re.DOTALL
        )

        creates = create_pattern.findall(content)
        updates = update_file_pattern.findall(content)

        if not creates and not updates:
            return "【补丁失败】：未检测到有效的补丁格式。请使用 '*** Create File:' 或 '*** Update File:'。"

        # 核心安全模式审批 (ASK 模式下应用源码补丁需人工确认)
        from tools.framework.policies import default_policy
        if default_policy.mode in ("ask", "always_ask") and not default_policy.session_approved:
            targets = [c[0].strip() for c in creates] + [u[0].strip() for u in updates]
            files_desc = ", ".join(targets[:5]) + ("..." if len(targets) > 5 else "")
            is_approved = default_policy.request_approval(
                f"apply_patch(files=[{files_desc}])",
                f"源码补丁变更（涉及 {len(targets)} 个文件: {files_desc}）"
            )
            if not is_approved:
                return f"【用户拒绝】：用户在终端取消或拒绝了对文件 [{files_desc}] 的补丁修改。"

        # 2. 事务级保护：若多文件中任一文件执行失败，立即全部回滚
        with PatchTransaction(default_snapshot_manager) as tx:
            # 先处理所有创建
            for filepath, file_body in creates:
                ok, res = _apply_create_file(filepath.strip(), file_body.strip("\r\n") + "\n", tx)
                if not ok:
                    tx.rollback()
                    return f"【补丁事务已回滚】：创建文件 '{filepath}' 失败，所有改动已恢复。\n原因: {res}"
                results.append(res)

            # 再处理所有更新
            for filepath, body, _ in updates:
                clean_path = filepath.strip()
                blocks = block_pattern.findall(body)
                if not blocks:
                    tx.rollback()
                    return f"【补丁事务已回滚】：未在 Update File '{clean_path}' 中找到有效的 SEARCH/REPLACE 块，所有改动已恢复。"

                ok, res = _apply_update_blocks(clean_path, blocks, tx)
                if not ok:
                    tx.rollback()
                    return f"【补丁事务已回滚】：修改文件 '{clean_path}' 失败，本次修改的所有文件已自动恢复原状。\n原因: {res}"
                results.append(res)

            # 全部文件与块修改成功，提交事务
            tx.commit()

        return "\n".join(results)

    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"【应用补丁出错】: {type(e).__name__}: {str(e)}"
