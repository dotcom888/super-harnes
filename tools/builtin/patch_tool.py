# -*- coding: utf-8 -*-
import re
from pathlib import Path
from typing import List, Tuple
from tools.registry import register_tool

# 当前项目安全根工作区
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

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

# 核心自保护名单：防止大模型通过补丁篡改自身的安全沙箱模块
CORE_PROTECTED_FILES = {
    "tools/file_tools.py",
    "tools/patch_tool.py",
    "tools/registry.py",
    "tools/executor.py",
}

def _validate_patch_target(target_path_str: str) -> Path:
    """
    针对文件写入操作的严苛安全校验：
    1. 规范化绝对路径，杜绝 ../ 路径穿越；
    2. 沙箱校验：必须严格在 WORKSPACE_ROOT 内部；
    3. 敏感凭证与环境资产保护；
    4. Agent 核心安全组件自保护。
    """
    target = Path(target_path_str)
    if not target.is_absolute():
        resolved = (WORKSPACE_ROOT / target).resolve()
    else:
        resolved = target.resolve()

    # 1. 沙箱越界校验
    try:
        relative_path = resolved.relative_to(WORKSPACE_ROOT)
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

    # 3. 核心自身源码保护（将路径转为 POSIX 风格校验）
    norm_rel = relative_path.as_posix()
    if norm_rel in CORE_PROTECTED_FILES:
        raise PermissionError(
            f"【安全拦截】：'{norm_rel}' 属于 Agent 核心安全引擎文件，已被设为只读保护！"
        )

    return resolved

def _apply_create_file(file_path_str: str, content: str) -> str:
    """安全创建新文件"""
    resolved_path = _validate_patch_target(file_path_str)
    # 创建所有必需的父级文件夹
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    # 写入内容
    with open(resolved_path, "w", encoding="utf-8") as f:
        f.write(content)

    return f"【创建成功】文件 '{file_path_str}' 已成功创建（共 {len(content)} 字符）。"

def _apply_update_blocks(file_path_str: str, blocks: List[Tuple[str, str]]) -> str:
    """对已有文件应用锚点替换块"""
    resolved_path = _validate_patch_target(file_path_str)

    if not resolved_path.exists() or not resolved_path.is_file():
        return f"【补丁失败】目标文件 '{file_path_str}' 不存在，无法应用更新补丁。"

    # 读取原文件内容
    with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
        original_content = f.read()

    modified_content = original_content

    for idx, (search_block, replace_block) in enumerate(blocks, start=1):
        if not search_block:
            continue

        # 校验锚点唯一性
        occurrences = modified_content.count(search_block)
        if occurrences == 0:
            # 宽容处理换行符风格差异（\r\n 与 \n）
            norm_mod = modified_content.replace("\r\n", "\n")
            norm_search = search_block.replace("\r\n", "\n")
            if norm_mod.count(norm_search) == 1:
                norm_replace = replace_block.replace("\r\n", "\n")
                modified_content = norm_mod.replace(norm_search, norm_replace, 1)
                continue
            return (
                f"【补丁失败】：在文件第 {idx} 个修改块中未找到匹配的 SEARCH 锚点代码。\n"
                f"请确保 SEARCH 中的代码与原文件完全一致（包含缩进和空行）。"
            )
        elif occurrences > 1:
            return (
                f"【补丁失败】：在文件中找到了 {occurrences} 处相同的 SEARCH 锚点代码，"
                f"定位不唯一！请在 SEARCH 块中增加上下文（前后几行代码）以准确定位。"
            )

        # 执行替换
        modified_content = modified_content.replace(search_block, replace_block, 1)

    # 全部块替换成功后，原子写入文件
    with open(resolved_path, "w", encoding="utf-8") as f:
        f.write(modified_content)

    return f"【补丁成功】文件 '{file_path_str}' 已成功修改，共完成 {len(blocks)} 处代码块替换。"

@register_tool(
    name="apply_patch",
    description="""用于精准修改现有文件或创建新文件的补丁工具。
格式说明：
1. 创建新文件：
*** Create File: 相对路径
新文件全部内容
*** End File

2. 修改现有文件（使用精准 SEARCH/REPLACE 块）：
*** Update File: 相对路径
<<<<<<< SEARCH
要被替换的原始代码（必须与原文件中的字符、缩进完全一致）
=======
替换后的新代码
>>>>>>> REPLACE
""",
    param_descriptions={
        "patch_content": "补丁指令字符串，包含 *** Create File 或 *** Update File 块"
    }
)
def apply_patch(patch_content: str) -> str:
    """解析并应用补丁的主入口"""
    try:
        content = patch_content.strip()
        results = []

        # 模式 1：Create File 匹配
        create_pattern = re.compile(
            r"\*\*\*\s*Create File:\s*(.*?)\n(.*?)(?:\n\*\*\*\s*End File|\Z)",
            re.DOTALL
        )
        creates = create_pattern.findall(content)
        for filepath, file_body in creates:
            res = _apply_create_file(filepath.strip(), file_body.strip("\r\n") + "\n")
            results.append(res)

        # 模式 2：Update File 匹配
        update_file_pattern = re.compile(
            r"\*\*\*\s*Update File:\s*([^\n]+)(.*?)(?=(\*\*\*\s*(?:Update|Create) File:)|\Z)",
            re.DOTALL
        )
        block_pattern = re.compile(
            r"<<<<<<<\s*SEARCH\n(.*?)=======\n(.*?)>>>>>>>\s*REPLACE",
            re.DOTALL
        )

        updates = update_file_pattern.findall(content)
        for filepath, body, _ in updates:
            filepath = filepath.strip()
            blocks = block_pattern.findall(body)
            if not blocks:
                results.append(f"【补丁格式错误】：未在 Update File '{filepath}' 中找到有效的 SEARCH/REPLACE 块。")
                continue
            res = _apply_update_blocks(filepath, blocks)
            results.append(res)

        if not results:
            return "【补丁失败】：未检测到有效的补丁格式。请使用 '*** Create File:' 或 '*** Update File:'。"

        return "\n".join(results)

    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"【应用补丁出错】: {type(e).__name__}: {str(e)}"
