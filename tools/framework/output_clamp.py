# -*- coding: utf-8 -*-
"""
tools/framework/output_clamp.py: 工业级多级语义压缩与溢出转存透镜架构 (Output Optimization & Spooling)
为 Agent 体系提供核心保障：
1. 物理全量安全落盘 (Spillover Buffer) 与 LRU 滚动容量上限淘汰；
2. 差异化语义特征提取器 (Semantic Extractor)，针对 Shell、Grep、通用工具精准捕获核心诊断；
3. 动态水位预算联动 (Watermark-Driven Clamping)，自适应上下文使用率；
4. 细节追查透镜指针 (Lens Pointer)，保留可二次检索追查能力。
"""
import re
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from collections import Counter

from tools.framework.workspace import default_workspace

logger = logging.getLogger(__name__)

# 核心编译、测试与代码诊断关键错误正则，优先锁定核心错误行与堆栈
ERROR_PATTERNS = [
    re.compile(r"(Traceback \(most recent call last\):[\s\S]+?)(?=\n\S|\Z)", re.IGNORECASE),
    re.compile(r"(\b(?:FAILED|AssertionError|\w*Error|\w*Exception):.*)", re.IGNORECASE),
    re.compile(r"(\b(?:\w+\.py|\w+\.ts|\w+\.rs|\w+\.go|\w+\.cpp|\w+\.c):\d+:\d+:.*(?:error|fatal):.*)", re.IGNORECASE),
    re.compile(r"(\b(?:FAILURES|ERRORS)\b[\s\S]+?)(?=\n={5,}|\Z)", re.IGNORECASE)
]

# 水位对应的自适应单步输出字符预算
WATERMARK_CHAR_QUOTAS = {
    "GREEN": 20000,   # 充裕区 (< 60%): 充分保留长上下文与完整堆栈
    "YELLOW": 7000,   # 警戒区 (60% ~ 75%): 聚焦关键行与紧凑堆栈
    "RED": 2500       # 告急区 (>= 75%): 强力精炼，仅保留核心异常与追查透镜
}

def get_tmp_spool_dir() -> Path:
    """获取并确保工作区临时溢出转存目录存在"""
    p = default_workspace.root / ".super-harnes" / "tmp"
    p.mkdir(parents=True, exist_ok=True)
    return p

def cleanup_old_spool_files(tmp_dir: Optional[Path] = None, max_files: int = 100, retain_files: int = 70):
    """
    轻量级滚动淘汰机制 (LRU Spool Cleanup):
    当临时转存目录文件数超过 max_files 时，按修改时间自动淘汰最旧的文件至 retain_files 个，
    防止长期高频使用下磁盘空间无节制膨胀。
    """
    try:
        target_dir = tmp_dir or get_tmp_spool_dir()
        if not target_dir.exists():
            return
        files = [p for p in target_dir.glob("spool_*.log") if p.is_file()]
        # 兼容老版 mcp_ 开头的日志
        files.extend([p for p in target_dir.glob("mcp_*.log") if p.is_file()])
        if len(files) > max_files:
            files.sort(key=lambda p: p.stat().st_mtime)
            files_to_remove = files[: len(files) - retain_files]
            for f in files_to_remove:
                try:
                    f.unlink()
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"清理临时转存文件异常: {e}")

def spool_to_disk(
    raw_text: str,
    tool_name: str = "tool",
    error_anchor: Optional[Tuple[int, int]] = None
) -> Tuple[Optional[Path], str]:
    """
    将海量原始文本安全全量落盘，并生成追查透镜提示字符串（支持报错行号锚点一键直达）。
    返回: (spool_file_path, lens_hint_string)
    """
    cleanup_old_spool_files()
    timestamp = int(time.time() * 1000)
    clean_tool = re.sub(r"[^\w\-]", "_", tool_name)[:30]
    spool_file = get_tmp_spool_dir() / f"spool_{clean_tool}_{timestamp}.log"
    try:
        spool_file.write_text(raw_text, encoding="utf-8", errors="replace")
        try:
            rel_path = spool_file.relative_to(default_workspace.root).as_posix()
        except Exception:
            rel_path = str(spool_file)
        
        line_count = len(raw_text.splitlines())
        size_kb = len(raw_text.encode("utf-8", errors="replace")) / 1024.0

        anchor_desc = ""
        if error_anchor and isinstance(error_anchor, (tuple, list)) and len(error_anchor) >= 2:
            err_start, err_end = error_anchor[0], error_anchor[1]
            suggest_start = max(1, err_start - 3)
            suggest_lines = min(150, max(20, err_end - err_start + 10))
            anchor_desc = (
                f"核心报错位于该文件第 {err_start} ~ {err_end} 行。"
                f"如需查看完整堆栈上下文，推荐直接执行: read_file(file_path='{rel_path}', start_line={suggest_start}, max_lines={suggest_lines})。"
            )

        lens_hint = (
            f"\n\n[系统提示: 完整原始输出 (共 {line_count} 行，{size_kb:.1f} KB) 已持久化至: {rel_path}。"
            f"{anchor_desc}"
            f"如需检索未展示细节，请使用 grep_text 检索该文件，或通过 read_file 分页查看]"
        )
        return spool_file, lens_hint
    except Exception as e:
        logger.warning(f"全量输出落盘失败: {e}")
        return None, ""

def clamp_shell_output(
    raw_text: str,
    max_chars: int = 8000,
    tool_name: str = "run_shell"
) -> str:
    """
    针对终端 Shell（构建、测试 pytest、执行命令等）的语义优先特征提取与截断：
    1. 若未超限，原样返回；
    2. 超限时物理落盘，生成追查透镜；
    3. 保留头部上下文（执行环境、参数）；
    4. 深度扫描并保留所有的核心错误、Traceback、失败断言与总结行；
    5. 折叠中间冗余通过日志；
    6. 硬配额终极保底，绝对不击穿 max_chars。
    """
    if len(raw_text) <= max_chars:
        return raw_text

    lines = raw_text.splitlines()
    total_lines = len(lines)

    # 1. 尝试抓取核心错误块与堆栈，并定位报错在原始输出中的确切行号锚点 (Anchor-Indexed Lens)
    matched_errors: List[str] = []
    first_anchor: Optional[Tuple[int, int]] = None
    for pattern in ERROR_PATTERNS:
        for m in pattern.finditer(raw_text):
            clean_m = m.group(0).strip()
            if clean_m and clean_m not in matched_errors:
                matched_errors.append(clean_m)
                if first_anchor is None:
                    err_start_line = raw_text[:m.start()].count('\n') + 1
                    err_end_line = err_start_line + clean_m.count('\n')
                    first_anchor = (err_start_line, err_end_line)
            if len(matched_errors) >= 4:
                break
        if len(matched_errors) >= 4:
            break

    _, lens_hint = spool_to_disk(raw_text, tool_name=tool_name, error_anchor=first_anchor)
    lens_hint_len = len(lens_hint)
    overhead = 120
    usable_chars = max(200, max_chars - lens_hint_len - overhead)

    # 2. 如果存在核心报错
    if matched_errors:
        raw_error_summary = "\n--- [核心错误与堆栈提取] ---\n" + "\n\n".join(matched_errors)
        max_error_budget = int(usable_chars * 0.75)
        if len(raw_error_summary) > max_error_budget:
            head_err_len = int(max_error_budget * 0.6)
            tail_err_len = int(max_error_budget * 0.35)
            error_summary = (
                f"{raw_error_summary[:head_err_len]}\n"
                f"... [堆栈过长已自动精简中间重复帧] ...\n"
                f"{raw_error_summary[-tail_err_len:]}"
            )
        else:
            error_summary = raw_error_summary

        allowed_head_len = max(50, int((usable_chars - len(error_summary)) * 0.6))
        allowed_tail_len = max(50, usable_chars - len(error_summary) - allowed_head_len)

        head_part = raw_text[:allowed_head_len].rstrip()
        tail_part = raw_text[-allowed_tail_len:].lstrip()

        result = (
            f"{head_part}\n\n"
            f"... [已保护性省略中间日志，核心诊断如下] ...\n"
            f"{error_summary}\n\n"
            f"... [尾部摘要] ...\n"
            f"{tail_part}{lens_hint}"
        )
        if len(result) > max_chars:
            result = result[:max_chars - 30] + "\n...[超限硬截断]..."
        return result

    # 3. 若无明确正则报错，但输出过长（如超长普通日志），保留首尾行
    line_quota = max(3, int(usable_chars / 150))
    head_lines = lines[:line_quota]
    tail_lines = lines[-line_quota:] if len(lines) > line_quota else []
    omitted_lines = max(0, total_lines - len(head_lines) - len(tail_lines))

    head_str = "\n".join(head_lines)
    tail_str = "\n".join(tail_lines)

    result = (
        f"{head_str}\n\n"
        f"... [输出过长，已保护性省略中间 {omitted_lines} 行日志] ...\n\n"
        f"{tail_str}{lens_hint}"
    )
    if len(result) > max_chars:
        result = result[:max_chars - 30] + "\n...[超限硬截断]..."
    return result

def clamp_search_output(
    raw_text: str,
    matches: List[str],
    max_chars: int = 8000,
    max_samples: int = 20,
    keyword: str = "",
    file_pattern: str = "*"
) -> str:
    """
    针对 grep_text / find_by_name 等检索类工具的海量匹配输出优化：
    1. 当命中数量适中时（如 <= 30 条且未超字符），原样输出；
    2. 当命中条数极大（如几百上千条）时，转为“文件分布热力图 + 代表性样本展示 + 缩小范围指引”；
    3. 全量落盘并返回追查透镜。
    """
    total_matches = len(matches)
    if len(raw_text) <= max_chars and total_matches <= 35:
        return raw_text

    _, lens_hint = spool_to_disk(raw_text, tool_name="grep_text")

    # 统计命中文件分布
    file_counts = Counter()
    for m in matches:
        parts = m.split(":", 1)
        if len(parts) >= 2:
            file_counts[parts[0].strip()] += 1
        else:
            file_counts["其他"] += 1

    total_files = len(file_counts)
    top_files = file_counts.most_common(5)
    top_files_desc = ", ".join([f"`{f}` ({c} 处)" for f, c in top_files])

    sample_matches = matches[:max_samples]
    samples_str = "\n".join(sample_matches)

    summary_card = (
        f"【代码搜索聚合】：命中数量过多，共找到 {total_matches} 处匹配，分布在 {total_files} 个文件中。\n"
        f"高频分布文件: {top_files_desc}\n\n"
        f"--- [代表性前 {len(sample_matches)} 条匹配样本] ---\n"
        f"{samples_str}\n\n"
        f"... [已省略其余 {total_matches - len(sample_matches)} 处匹配] ...\n\n"
        f"【检索优化建议】：匹配量过大，建议在调用 grep_text 时传入 'directory' 参数指定排查子目录，"
        f"或限定 'file_pattern' (如 '*.py')，或增加更精确的关键字。"
        f"{lens_hint}"
    )

    if len(summary_card) > max_chars:
        summary_card = summary_card[:max_chars - 30] + "\n...[超限硬截断]..."
    return summary_card

def clamp_generic_output(
    raw_text: str,
    max_chars: int = 10000,
    tool_name: str = "tool"
) -> str:
    """
    通用语义输出保护器（供 MCP 工具及 Agent 单步通用兜底使用）：
    1. 超限全量落盘；
    2. 优先保留正则异常与堆栈；
    3. 保留首尾；
    4. 附带追查透镜提示。
    """
    return clamp_shell_output(raw_text, max_chars=max_chars, tool_name=tool_name)

def get_dynamic_max_chars(zone: Optional[str] = "GREEN") -> int:
    """根据当前上下文水位获取建议的单步工具输出上限"""
    if not zone:
        return WATERMARK_CHAR_QUOTAS["GREEN"]
    return WATERMARK_CHAR_QUOTAS.get(zone.upper(), WATERMARK_CHAR_QUOTAS["GREEN"])
