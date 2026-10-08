
import copy
import xml.etree.ElementTree as ET
import zipfile
import re
import os
import win32com.client
import fitz

W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
W14_NS = 'http://schemas.microsoft.com/office/word/2010/wordml'
WPS_NS = 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape'
WP_NS = 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
A_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
MC_NS = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
V_NS = 'urn:schemas-microsoft-com:vml'

ns = {
    'w': W_NS,
    'wp': WP_NS,
    'a': A_NS,
    'wps': WPS_NS,
    'mc': MC_NS,
    'v': V_NS
}

def make_title_p(title_text, font_sz='20', line_sp='340', before='60', after='20'):
    p = ET.Element(f'{{{W_NS}}}p')
    pPr = ET.SubElement(p, f'{{{W_NS}}}pPr')
    ET.SubElement(pPr, f'{{{W_NS}}}spacing', attrib={
        f'{{{W_NS}}}line': str(line_sp),
        f'{{{W_NS}}}lineRule': 'exact',
        f'{{{W_NS}}}before': str(before),
        f'{{{W_NS}}}after': str(after)
    })
    rPr = ET.SubElement(pPr, f'{{{W_NS}}}rPr')
    ET.SubElement(rPr, f'{{{W_NS}}}rFonts', attrib={
        f'{{{W_NS}}}hint': 'eastAsia',
        f'{{{W_NS}}}ascii': '微软雅黑',
        f'{{{W_NS}}}hAnsi': '微软雅黑',
        f'{{{W_NS}}}eastAsia': '微软雅黑'
    })
    ET.SubElement(rPr, f'{{{W_NS}}}b')
    ET.SubElement(rPr, f'{{{W_NS}}}bCs')
    ET.SubElement(rPr, f'{{{W_NS}}}color', attrib={f'{{{W_NS}}}val': '0091BD'})
    ET.SubElement(rPr, f'{{{W_NS}}}sz', attrib={f'{{{W_NS}}}val': str(font_sz)})
    ET.SubElement(rPr, f'{{{W_NS}}}szCs', attrib={f'{{{W_NS}}}val': str(font_sz)})
    
    r = ET.SubElement(p, f'{{{W_NS}}}r')
    r_rPr = ET.SubElement(r, f'{{{W_NS}}}rPr')
    ET.SubElement(r_rPr, f'{{{W_NS}}}rFonts', attrib={
        f'{{{W_NS}}}hint': 'eastAsia',
        f'{{{W_NS}}}ascii': '微软雅黑',
        f'{{{W_NS}}}hAnsi': '微软雅黑',
        f'{{{W_NS}}}eastAsia': '微软雅黑'
    })
    ET.SubElement(r_rPr, f'{{{W_NS}}}b')
    ET.SubElement(r_rPr, f'{{{W_NS}}}bCs')
    ET.SubElement(r_rPr, f'{{{W_NS}}}color', attrib={f'{{{W_NS}}}val': '0091BD'})
    ET.SubElement(r_rPr, f'{{{W_NS}}}sz', attrib={f'{{{W_NS}}}val': str(font_sz)})
    ET.SubElement(r_rPr, f'{{{W_NS}}}szCs', attrib={f'{{{W_NS}}}val': str(font_sz)})
    t = ET.SubElement(r, f'{{{W_NS}}}t')
    t.text = title_text
    return p

def make_bullet_p(label, content, font_sz='18', line_sp='290', after='15', label_color='0091BD'):
    p = ET.Element(f'{{{W_NS}}}p')
    pPr = ET.SubElement(p, f'{{{W_NS}}}pPr')
    numPr = ET.SubElement(pPr, f'{{{W_NS}}}numPr')
    ET.SubElement(numPr, f'{{{W_NS}}}ilvl', attrib={f'{{{W_NS}}}val': '0'})
    ET.SubElement(numPr, f'{{{W_NS}}}numId', attrib={f'{{{W_NS}}}val': '1'})
    ET.SubElement(pPr, f'{{{W_NS}}}spacing', attrib={
        f'{{{W_NS}}}line': str(line_sp),
        f'{{{W_NS}}}lineRule': 'exact',
        f'{{{W_NS}}}after': str(after)
    })
    rPr = ET.SubElement(pPr, f'{{{W_NS}}}rPr')
    ET.SubElement(rPr, f'{{{W_NS}}}rFonts', attrib={
        f'{{{W_NS}}}hint': 'eastAsia',
        f'{{{W_NS}}}ascii': '微软雅黑',
        f'{{{W_NS}}}hAnsi': '微软雅黑',
        f'{{{W_NS}}}eastAsia': '微软雅黑'
    })
    ET.SubElement(rPr, f'{{{W_NS}}}color', attrib={f'{{{W_NS}}}val': '000000'})
    ET.SubElement(rPr, f'{{{W_NS}}}sz', attrib={f'{{{W_NS}}}val': str(font_sz)})
    ET.SubElement(rPr, f'{{{W_NS}}}szCs', attrib={f'{{{W_NS}}}val': str(font_sz)})
    
    if label:
        r_lbl = ET.SubElement(p, f'{{{W_NS}}}r')
        r_lbl_pr = ET.SubElement(r_lbl, f'{{{W_NS}}}rPr')
        ET.SubElement(r_lbl_pr, f'{{{W_NS}}}rFonts', attrib={
            f'{{{W_NS}}}hint': 'eastAsia',
            f'{{{W_NS}}}ascii': '微软雅黑',
            f'{{{W_NS}}}hAnsi': '微软雅黑',
            f'{{{W_NS}}}eastAsia': '微软雅黑'
        })
        ET.SubElement(r_lbl_pr, f'{{{W_NS}}}b')
        ET.SubElement(r_lbl_pr, f'{{{W_NS}}}bCs')
        ET.SubElement(r_lbl_pr, f'{{{W_NS}}}color', attrib={f'{{{W_NS}}}val': label_color})
        ET.SubElement(r_lbl_pr, f'{{{W_NS}}}sz', attrib={f'{{{W_NS}}}val': str(font_sz)})
        ET.SubElement(r_lbl_pr, f'{{{W_NS}}}szCs', attrib={f'{{{W_NS}}}val': str(font_sz)})
        t_lbl = ET.SubElement(r_lbl, f'{{{W_NS}}}t')
        t_lbl.text = label
        
    if content:
        r_cnt = ET.SubElement(p, f'{{{W_NS}}}r')
        r_cnt_pr = ET.SubElement(r_cnt, f'{{{W_NS}}}rPr')
        ET.SubElement(r_cnt_pr, f'{{{W_NS}}}rFonts', attrib={
            f'{{{W_NS}}}ascii': '微软雅黑',
            f'{{{W_NS}}}hAnsi': '微软雅黑',
            f'{{{W_NS}}}eastAsia': '微软雅黑'
        })
        ET.SubElement(r_cnt_pr, f'{{{W_NS}}}color', attrib={f'{{{W_NS}}}val': '000000'})
        ET.SubElement(r_cnt_pr, f'{{{W_NS}}}sz', attrib={f'{{{W_NS}}}val': str(font_sz)})
        ET.SubElement(r_cnt_pr, f'{{{W_NS}}}szCs', attrib={f'{{{W_NS}}}val': str(font_sz)})
        t_cnt = ET.SubElement(r_cnt, f'{{{W_NS}}}t')
        t_cnt.text = content
    return p

def make_normal_p(runs_data, font_sz='18', line_sp='290', before='0', after='15'):
    p = ET.Element(f'{{{W_NS}}}p')
    pPr = ET.SubElement(p, f'{{{W_NS}}}pPr')
    ET.SubElement(pPr, f'{{{W_NS}}}spacing', attrib={
        f'{{{W_NS}}}line': str(line_sp),
        f'{{{W_NS}}}lineRule': 'exact',
        f'{{{W_NS}}}before': str(before),
        f'{{{W_NS}}}after': str(after)
    })
    rPr = ET.SubElement(pPr, f'{{{W_NS}}}rPr')
    ET.SubElement(rPr, f'{{{W_NS}}}rFonts', attrib={
        f'{{{W_NS}}}hint': 'eastAsia',
        f'{{{W_NS}}}ascii': '微软雅黑',
        f'{{{W_NS}}}hAnsi': '微软雅黑',
        f'{{{W_NS}}}eastAsia': '微软雅黑'
    })
    ET.SubElement(rPr, f'{{{W_NS}}}sz', attrib={f'{{{W_NS}}}val': str(font_sz)})
    ET.SubElement(rPr, f'{{{W_NS}}}szCs', attrib={f'{{{W_NS}}}val': str(font_sz)})
    
    for text, is_bold, color in runs_data:
        r = ET.SubElement(p, f'{{{W_NS}}}r')
        r_pr = ET.SubElement(r, f'{{{W_NS}}}rPr')
        ET.SubElement(r_pr, f'{{{W_NS}}}rFonts', attrib={
            f'{{{W_NS}}}hint': 'eastAsia',
            f'{{{W_NS}}}ascii': '微软雅黑',
            f'{{{W_NS}}}hAnsi': '微软雅黑',
            f'{{{W_NS}}}eastAsia': '微软雅黑'
        })
        if is_bold:
            ET.SubElement(r_pr, f'{{{W_NS}}}b')
            ET.SubElement(r_pr, f'{{{W_NS}}}bCs')
        if color:
            ET.SubElement(r_pr, f'{{{W_NS}}}color', attrib={f'{{{W_NS}}}val': color})
        ET.SubElement(r_pr, f'{{{W_NS}}}sz', attrib={f'{{{W_NS}}}val': str(font_sz)})
        ET.SubElement(r_pr, f'{{{W_NS}}}szCs', attrib={f'{{{W_NS}}}val': str(font_sz)})
        t = ET.SubElement(r, f'{{{W_NS}}}t')
        t.text = text
    return p

print('Helper functions compiled')
