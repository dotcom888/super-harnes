# -*- coding: utf-8 -*-
import os
import shutil
import sys

desktop = r'C:\Users\Administrator\Desktop'
game_folder = os.path.join(desktop, '坦克大战')
os.makedirs(game_folder, exist_ok=True)

# 1. 读取 Python Tkinter 版代码
with open('tank_game_tkinter.py', 'r', encoding='utf-8') as f:
    tank_code = f.read()

# 写入桌面
desk_pyw = os.path.join(desktop, '坦克大战.pyw')
folder_pyw = os.path.join(game_folder, '坦克大战.pyw')
with open(desk_pyw, 'w', encoding='utf-8') as f:
    f.write(tank_code)
with open(folder_pyw, 'w', encoding='utf-8') as f:
    f.write(tank_code)

# 2. 读取 HTML 版代码并确保桌面与文件夹均有
with open(os.path.join(desktop, '坦克大战.html'), 'r', encoding='utf-8') as f:
    html_code = f.read()

with open(os.path.join(game_folder, '坦克大战_经典网页版.html'), 'w', encoding='utf-8') as f:
    f.write(html_code)

# 3. 生成批处理启动脚本
python_exe = sys.executable
# 获取 pythonw.exe 路径
pythonw_exe = os.path.join(os.path.dirname(python_exe), 'pythonw.exe')
if not os.path.exists(pythonw_exe):
    pythonw_exe = python_exe

bat_content = f'''@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "{pythonw_exe}" (
    start "" "{pythonw_exe}" "坦克大战.pyw"
) else (
    start "" pythonw "坦克大战.pyw"
)
exit
'''

with open(os.path.join(desktop, '启动坦克大战(桌面版).bat'), 'w', encoding='utf-8') as f:
    f.write(bat_content)

with open(os.path.join(game_folder, '启动坦克大战.bat'), 'w', encoding='utf-8') as f:
    f.write(bat_content)

# 4. 游戏说明说明书
readme = '''==============================================
       经典坦克大战 1990 (BATTLE CITY) 典藏版
==============================================

已为您成功在桌面安装《坦克大战 1990》双版本，双击即可畅玩！

【方式 1：经典网页版 (强烈推荐，原汁原味音画)】
  - 路径：桌面【坦克大战.html】
  - 特色：无需任何外部依赖，支持全屏幕与双人作战！
  - 内置真实 8-bit FC 经典音效（白噪声大爆炸、激光射击、吃道具琶音）！
  - 拥有 5 大经典关卡，道具掉落，重炮打碎铁墙！

【方式 2：桌面客户端版 (原生独立窗口)】
  - 路径：桌面【启动坦克大战(桌面版).bat】或【坦克大战.pyw】
  - 特色：Python Tkinter 原生 GUI 窗口，纯净无控制台黑框！

----------------------------------------------
【游戏操作说明】
  ★ 1P 玩家操作：
     - 移动：W / A / S / D  或  方向键 ↑ ↓ ← →
     - 开火：J 键  或  空格键 (Space)
  ★ 2P 玩家操作（网页版双人模式）：
     - 移动：方向键 ↑ ↓ ← →
     - 开火：Enter 键  或  小键盘 0
  ★ 通用控制：
     - P 键：暂停 / 继续游戏
     - R 键：重新开始游戏

----------------------------------------------
【道具系统说明】
  ★ 五角星 (★)：坦克火力升级（可升到最高级破拆钢墙）
  ★ 炸弹 (💣)：全屏敌方坦克瞬间引爆
  ★ 定时钟 (⏱)：敌方全员定身冰冻 10 秒
  ★ 铁锹 (⛏)：将老鹰老巢四周临时变为钢铁堡垒
  ★ 防护钢盔 (🛡)：获得无敌力场护盾圈
  ★ 红心战车 (❤)：生命值 +1 (1UP)

保护老鹰基地，消灭所有敌军坦克！
==============================================
'''

with open(os.path.join(desktop, '坦克大战玩法说明.txt'), 'w', encoding='utf-8') as f:
    f.write(readme)
with open(os.path.join(game_folder, '玩法说明.txt'), 'w', encoding='utf-8') as f:
    f.write(readme)

print("DEPLOY_SUCCESS")
