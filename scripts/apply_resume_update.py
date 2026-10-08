# -*- coding: utf-8 -*-
import sys
import copy
import xml.etree.ElementTree as ET
import zipfile
import re
import os
import win32com.client
import fitz
from build_resume_helpers import make_title_p, make_bullet_p, make_normal_p, W_NS, WPS_NS, WP_NS, A_NS, MC_NS, V_NS, ns

def update_anchor_box(item, y_emu, cy_emu):
    # Choice (DrawingML)
    anc = item.find('.//wp:anchor', ns)
    if anc is not None:
        pos_v = anc.find('wp:positionV/wp:posOffset', ns)
        if pos_v is not None:
            pos_v.text = str(y_emu)
        ext = anc.find('wp:extent', ns)
        if ext is not None:
            ext.attrib['cy'] = str(cy_emu)
        xfrm_ext = anc.find('.//a:xfrm/a:ext', ns)
        if xfrm_ext is not None:
            xfrm_ext.attrib['cy'] = str(cy_emu)
            
    # Fallback (VML)
    v_shape = item.find('.//v:shape', ns)
    if v_shape is not None and 'style' in v_shape.attrib:
        st = v_shape.attrib['style']
        y_pt = y_emu / 12700.0
        cy_pt = cy_emu / 12700.0
        # replace margin-top and height if present
        if 'margin-top:' in st:
            st = re.sub(r'margin-top:[^;]+', f'margin-top:{y_pt:.1f}pt', st)
        if 'height:' in st:
            st = re.sub(r'height:[^;]+', f'height:{cy_pt:.1f}pt', st)
        v_shape.attrib['style'] = st

def replace_txbx_content(item, new_paragraphs):
    # Choice
    txbx_c = item.find('.//mc:Choice//wps:txbx/w:txbxContent', ns)
    if txbx_c is not None:
        txbx_c.clear()
        for p in new_paragraphs:
            txbx_c.append(copy.deepcopy(p))
            
    # Fallback
    txbx_f = item.find('.//mc:Fallback//v:textbox/w:txbxContent', ns)
    if txbx_f is not None:
        txbx_f.clear()
        for p in new_paragraphs:
            txbx_f.append(copy.deepcopy(p))

def process():
    docx_path = 'D:/dxzy/byl/求职/简历/叶华萌2609-模板.docx'
    with zipfile.ZipFile(docx_path) as z:
        files = {name: z.read(name) for name in z.namelist()}

    root = ET.fromstring(files['word/document.xml'])
    body = root.find('w:body', ns)
    ps = body.findall('w:p', ns)
    
    # Remove extra paragraphs p1 and p2 to eliminate page 2 overflow
    while len(ps) > 1:
        body.remove(ps[-1])
        ps = body.findall('w:p', ns)

    p0 = ps[0]
    
    # Update Item 11: Header (Name & Target Role)
    item11 = p0[11]
    # Update 求职意向 to AI Agent / 数据分析
    p_target = item11.find('.//mc:Choice//w:p[2]', ns)
    if p_target is not None:
        t_elem = p_target.find('.//w:t', ns)
        if t_elem is not None:
            t_elem.text = '求职意向：AI Agent / 数据分析'
    p_target_f = item11.find('.//mc:Fallback//w:p[2]', ns)
    if p_target_f is not None:
        t_elem_f = p_target_f.find('.//w:t', ns)
        if t_elem_f is not None:
            t_elem_f.text = '求职意向：AI Agent / 数据分析'

    # Coordinates budget (EMUs)
    # Section 1: 教育背景
    update_anchor_box(p0[10], y_emu=640000, cy_emu=359410)
    update_anchor_box(p0[9],  y_emu=930000, cy_emu=260000)
    update_anchor_box(p0[8],  y_emu=1170000, cy_emu=260000)
    
    # Clean Item 9 (School & Major)
    edu_school_p = [make_normal_p([
        ('2021.9 - 2025.6', True, '0091BD'),
        ('                                 广州应用科技学院                                ', True, '0091BD'),
        ('计算机科学与技术 / 本科', True, '0091BD')
    ], font_sz='19', line_sp='320', after='0')]
    replace_txbx_content(p0[9], edu_school_p)
    
    # Clean Item 8 (Courses)
    edu_courses_p = [make_normal_p([
        ('主修课程：', True, '0091BD'),
        ('计算机网络、计算机组成原理、机器学习、数据结构、人工智能、统计学、Python、MySQL 等', False, '000000')
    ], font_sz='18', line_sp='300', after='0')]
    replace_txbx_content(p0[8], edu_courses_p)

    # Section 2: 专业技能
    update_anchor_box(p0[7], y_emu=1440000, cy_emu=359410)
    update_anchor_box(p0[4], y_emu=1730000, cy_emu=920000)
    
    skills_ps = [
        make_normal_p([
            ('大模型与智能体：', True, '0091BD'),
            ('深入掌握 ReAct 推理闭环、任务状态机、Prompt 工程与 Function Calling；熟悉 MCP 协议、Token 预算滑窗与历史压缩、SKILL.md 技能生态', False, '000000')
        ], font_sz='18', line_sp='275', after='10'),
        make_normal_p([
            ('开发与工程化：', True, '0091BD'),
            ('精通 Python（熟练掌握 asyncio 异步编程、AST 语法树解析、多进程管理）；熟练掌握 Git 版本控制、pytest 自动化测试、影刀 RPA', False, '000000')
        ], font_sz='18', line_sp='275', after='10'),
        make_normal_p([
            ('数据分析与建模：', True, '0091BD'),
            ('熟练使用 Pandas、NumPy、Scikit-learn、SQL 进行数据清洗、特征工程与机器学习建模（LTV 模型）；熟练使用 Power BI（DAX 建模）与 Matplotlib', False, '000000')
        ], font_sz='18', line_sp='275', after='10'),
        make_normal_p([
            ('业务协同与交付：', True, '0091BD'),
            ('具备清晰的需求拆解、技术方案编写、流程图设计（Visio）、指标归因分析与跨部门协同推进能力，自驱力与抗压能力强', False, '000000')
        ], font_sz='18', line_sp='275', after='0')
    ]
    replace_txbx_content(p0[4], skills_ps)

    # Section 3: 项目经历
    update_anchor_box(p0[2], y_emu=2680000, cy_emu=359410)
    update_anchor_box(p0[1], y_emu=2970000, cy_emu=3820000)
    
    projects_ps = [
        # Project 1: Super-Harnes
        make_title_p('项目一：  Super-Harnes 工业级自主代码编程智能体', font_sz='19', line_sp='320', before='20', after='10'),
        make_bullet_p('项目背景：', '面向真实工程场景自主研发的高性能自主代码编程智能体，支持复杂长任务多步自主推理闭环与工程级代码修复。', font_sz='18', line_sp='270', after='10'),
        make_bullet_p('决策与状态机：', '基于 ReAct 闭环搭建 EXPLORE→MODIFY→VERIFY 状态机与自适应加权；研发三模式死循环熔断器（黄牌反思/红牌强制收敛），彻底杜绝无限空转。', font_sz='18', line_sp='270', after='10'),
        make_bullet_p('上下文预算：', '设计 200K~500K 弹性滑窗与分账账本（BudgetLedger）；首创 TurnChunk 原子绑定杜绝 tool_calls 孤儿截断；基于水位控制触发带锚点增量压缩。', font_sz='18', line_sp='270', after='10'),
        make_bullet_p('原子回滚与扩展：', '实现写前毫秒级 Shadow Snapshot 与多文件补丁事务回滚（Patch Transaction）；基于 MCP 0端口 Stdio 扩展与 SKILL.md 生态，145+ 测试全通过。', font_sz='18', line_sp='270', after='15'),

        # Project 2: 玩家游戏付费预测
        make_title_p('项目二：  玩家游戏付费金额预测 (SLG策略手游LTV建模)', font_sz='19', line_sp='320', before='15', after='10'),
        make_bullet_p('数据清洗与建模：', '基于 Pandas 提取清洗 200w 条原始日志，构建 45 日 LTV 预测模型与特征工程，利用 Scikit-learn 进行分组建模拟合与模型融合。', font_sz='18', line_sp='270', after='10'),
        make_bullet_p('业务效果：', '测试集模型拟合度达 R²=0.85；针对不同价值用户群体实施分层运营画像，有效指导运营活动优化，带动月活跃与付费收入增长。', font_sz='18', line_sp='270', after='15'),

        # Project 3: 自动售货机销售量分析
        make_title_p('项目三：  自动售货机销售量与经营分析', font_sz='19', line_sp='320', before='15', after='10'),
        make_bullet_p('数据建模与看板：', '使用 Power BI 对 11k 行销售及库存数据进行清洗与 DAX 建模，搭建多维交互式报表可视化分析销售额、订单量及 SKU 走势。', font_sz='18', line_sp='270', after='10'),
        make_bullet_p('业务效果：', '根据报表数据推动选品结构与补货机制优化，单机月均销售额提升 12%（在线作品看板：http://i7q.cn/5Uk0fr）。', font_sz='18', line_sp='270', after='0')
    ]
    replace_txbx_content(p0[1], projects_ps)

    # Section 4: 实习经历
    update_anchor_box(p0[0], y_emu=6830000, cy_emu=359410)
    update_anchor_box(p0[3], y_emu=7120000, cy_emu=1520000)
    
    intern_ps = [
        make_normal_p([
            ('2024.6 - 2024.8                             广东泰迪科技有限公司                             数据分析实习', True, '0091BD')
        ], font_sz='18', line_sp='300', before='10', after='10'),
        make_bullet_p('', '负责项目中数据模型构建、数据交换与清洗实施工作，支撑报表展示部门的指标开发与数据应用；', font_sz='18', line_sp='270', after='10'),
        make_bullet_p('', '编写 SQL 提取清洗多源异构数据，制作深度业务数据分析报告，为决策层提供数据量化支撑。', font_sz='18', line_sp='270', after='15'),
        
        make_normal_p([
            ('2024.10 - 2024.12                         广州景心科技股份有限公司                         运营助理实习生', True, '0091BD')
        ], font_sz='18', line_sp='300', before='10', after='10'),
        make_bullet_p('', '负责移动运营商门店业务协同与商品上架对接，保持与对应负责人高频沟通，确保信息准确流转；', font_sz='18', line_sp='270', after='10'),
        make_bullet_p('', '利用抖音平台数据分析工具对推广全链路数据进行深入分析（曝光量/点击率/转化率），优化运营动作。', font_sz='18', line_sp='270', after='0')
    ]
    replace_txbx_content(p0[3], intern_ps)

    # Section 5: 自我评价
    update_anchor_box(p0[5], y_emu=8680000, cy_emu=359410)
    update_anchor_box(p0[6], y_emu=8970000, cy_emu=620000)
    
    self_eval_ps = [
        make_normal_p([
            ('计算机专业科班出身，兼具算法模型与大模型 Agent 架构开发能力，拥有自主从 0 到 1 架构中大型开源智能体项目（Super-Harnes）的实战经历，自驱力与攻坚能力强。', False, '000000')
        ], font_sz='18', line_sp='280', after='10'),
        make_normal_p([
            ('具备知名大数据企业实习背景与全流程数据分析、建模及落地经验，逻辑严谨，业务理解深刻，沟通协作良好，能快速推动技术方案高质量落地。', False, '000000')
        ], font_sz='18', line_sp='280', after='0')
    ]
    replace_txbx_content(p0[6], self_eval_ps)

    # Save to docx
    files['word/document.xml'] = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    out_docx = 'D:/dxzy/byl/求职/简历/叶华萌2609-模板.docx'
    with zipfile.ZipFile(out_docx, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
    print('Updated docx saved successfully!')

if __name__ == '__main__':
    process()
