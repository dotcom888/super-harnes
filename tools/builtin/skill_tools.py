# -*- coding: utf-8 -*-
"""
tools/builtin/skill_tools.py: 专有领域专家技能 (Skills) 动态加载与查阅内置工具
遵循行业标准的 Just-In-Time 上下文按需加载机制
"""
from typing import Optional
from tools.registry import register_tool
# default_skill_manager imported inside functions to prevent circular import


@register_tool(
    name="load_skill",
    is_read_only=True,
    description="""动态按需加载并查阅指定领域专家技能 (Skill) 的完整 SOP 工作流程、执行准则与规约文档。
【选型准则与反向约束】：当你需要开展复杂工程排查、Bug 根因定位、代码审查或架构调整时，若系统提示词的可用技能库中存在匹配技能，必须先调用此工具载入对应领域的专家流程，严格遵循其 Phase 步骤与纪律进行推进，杜绝盲目修改代码。""",
    param_descriptions={
        "skill_name": "需要加载的技能名称，例如 'diagnosing-bugs'"
    }
)
def load_skill(skill_name: str) -> str:
    """动态加载技能正文并返回给模型作为 Observation"""
    from skills.manager import default_skill_manager
    if not skill_name or not skill_name.strip():
        return "【错误】未指定技能名称。可调用 list_available_skills 查看所有可用技能。"

    skill = default_skill_manager.get_skill(skill_name.strip())
    if not skill:
        available = [s.name for s in default_skill_manager.list_skills()]
        avail_str = ", ".join(available) if available else "无"
        return f"【未找到技能】名称为 '{skill_name}' 的技能不存在。当前已挂载技能列表: [{avail_str}]"

    content = skill.content
    if not content:
        return f"【警告】技能 '{skill.name}' 规约内容为空或读取失败 (路径: {skill.skill_file})。"

    output = [
        f"==================== 专有技能载入: 【{skill.name}】 ====================",
        f"作用域: {skill.source_scope} | 定义路径: {skill.skill_file}",
        f"适用场景: {skill.description}",
        "-------------------------------- SOP 执行规约 --------------------------------",
        content.strip(),
        "================================================================================"
    ]
    return "\n".join(output)


@register_tool(
    name="list_available_skills",
    is_read_only=True,
    description="查看当前智能体已感知识别的所有领域专家技能 (Skills) 列表、来源作用域及适用场景说明。",
    param_descriptions={}
)
def list_available_skills() -> str:
    """列出当前所有挂载的技能"""
    from skills.manager import default_skill_manager
    skills = default_skill_manager.list_skills()
    if not skills:
        return "当前尚未在工作区或用户目录检测到任何 SKILL.md 技能定义。"

    lines = [
        f"当前系统已挂载 {len(skills)} 个专家技能 (Skills):",
        "--------------------------------------------------------------------------------"
    ]
    for s in skills:
        lines.append(f"● {s.name:<25} [{s.source_scope}] - {s.description}")
    lines.append("--------------------------------------------------------------------------------")
    lines.append("💡 提示：可调用 load_skill(skill_name='...') 深入读取具体技能的 SOP 规约。")
    return "\n".join(lines)
