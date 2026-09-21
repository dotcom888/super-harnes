# -*- coding: utf-8 -*-
"""
经典坦克大战 1990 - Python 原生桌面典藏版
无需安装任何第三方库（基于 Python 标准库 tkinter）
双击即可独立窗口运行，自带 60 FPS 平滑动画、AI 巡逻、多种敌方坦克、升级道具系统！
"""

import tkinter as tk
import random
import math
import sys
import os

# ================= 经典常量 =================
CELL_SIZE = 20
GRID_ROWS = 26
GRID_COLS = 26
BOARD_SIZE = CELL_SIZE * GRID_ROWS  # 520 x 520

T_EMPTY = 0
T_BRICK = 1
T_STEEL = 2
T_GRASS = 3
T_WATER = 4
T_BASE  = 9

DIR_UP    = 0
DIR_DOWN  = 1
DIR_LEFT  = 2
DIR_RIGHT = 3

# 预设地图 1
MAP_PRESET = [
    "00000000000000000000000000",
    "00110011001100110011001100",
    "00110011001100110011001100",
    "00110011001100110011001100",
    "00110011001122110011001100",
    "00110011001122110011001100",
    "00110011000000000011001100",
    "00110011000000000011001100",
    "00000000001100110000000000",
    "22001111001100110011110022",
    "22001111000000000011110022",
    "00001111001111110011110000",
    "00000000001111110000000000",
    "00000000001100110000000000",
    "00110011001100110011001100",
    "00110011001100110011001100",
    "00110011000000000011001100",
    "00110011000000000011001100",
    "00110011001111110011001100",
    "00110011001111110011001100",
    "00110011000000000011001100",
    "00000000000000000000000000",
    "00000000000000000000000000",
    "00000000000111100000000000",
    "00000000000199100000000000",
    "00000000000199100000000000"
]

class Bullet:
    def __init__(self, x, y, direction, speed, is_player, owner, break_steel=False):
        self.x = x
        self.y = y
        self.dir = direction
        self.speed = speed
        self.is_player = is_player
        self.owner = owner
        self.break_steel = break_steel
        self.active = True

    def update(self):
        if not self.active:
            return
        if self.dir == DIR_UP:
            self.y -= self.speed
        elif self.dir == DIR_DOWN:
            self.y += self.speed
        elif self.dir == DIR_LEFT:
            self.x -= self.speed
        elif self.dir == DIR_RIGHT:
            self.x += self.speed

        if self.x < 0 or self.x > BOARD_SIZE or self.y < 0 or self.y > BOARD_SIZE:
            self.active = False

class Explosion:
    def __init__(self, x, y, is_big=False):
        self.x = x
        self.y = y
        self.is_big = is_big
        self.frame = 0
        self.max_frames = 15 if is_big else 8

    def update(self):
        self.frame += 1

    def is_finished(self):
        return self.frame >= self.max_frames

class PowerUp:
    STAR   = 1
    BOMB   = 2
    CLOCK  = 3
    SHOVEL = 4
    HELMET = 5
    TANK   = 6

    def __init__(self, x, y, p_type):
        self.x = x
        self.y = y
        self.type = p_type
        self.timer = 500  # 持续约 10 秒
        self.size = 22

    def update(self):
        self.timer -= 1

class TankObj:
    def __init__(self, x, y, direction, speed, color):
        self.x = x
        self.y = y
        self.size = 28
        self.dir = direction
        self.speed = speed
        self.color = color
        self.shield_timer = 0
        self.shoot_cd = 0

    def can_move(self, nx, ny, game_map):
        if nx < 0 or nx + self.size > BOARD_SIZE or ny < 0 or ny + self.size > BOARD_SIZE:
            return False
        left = int(nx // CELL_SIZE)
        right = int((nx + self.size - 1) // CELL_SIZE)
        top = int(ny // CELL_SIZE)
        bottom = int((ny + self.size - 1) // CELL_SIZE)

        for r in range(top, bottom + 1):
            for c in range(left, right + 1):
                if 0 <= r < GRID_ROWS and 0 <= c < GRID_COLS:
                    t = game_map[r][c]
                    if t in (T_BRICK, T_STEEL, T_WATER, T_BASE):
                        return False
        return True

class PlayerTank(TankObj):
    def __init__(self, x, y):
        super().__init__(x, y, DIR_UP, 3.0, "#e5a93b")
        self.lives = 3
        self.score = 0
        self.level = 0
        self.shield_timer = 150
        self.spawn_x = x
        self.spawn_y = y

    def respawn(self):
        self.x = self.spawn_x
        self.y = self.spawn_y
        self.dir = DIR_UP
        self.shield_timer = 150
        self.level = max(0, self.level - 1)

    def shoot(self, bullets):
        if self.shoot_cd > 0:
            return
        b_speed = 6.0 if self.level >= 1 else 4.5
        break_steel = (self.level >= 3)
        cx = self.x + self.size / 2
        cy = self.y + self.size / 2
        bx, by = cx, cy
        if self.dir == DIR_UP:
            by = self.y - 2
        elif self.dir == DIR_DOWN:
            by = self.y + self.size + 2
        elif self.dir == DIR_LEFT:
            bx = self.x - 2
        elif self.dir == DIR_RIGHT:
            bx = self.x + self.size + 2

        my_b = [b for b in bullets if b.owner == self and b.active]
        max_b = 2 if self.level >= 2 else 1
        if len(my_b) < max_b:
            bullets.append(Bullet(bx, by, self.dir, b_speed, True, self, break_steel))
            self.shoot_cd = 12

class EnemyTank(TankObj):
    BASIC = 1
    FAST  = 2
    POWER = 3
    ARMOR = 4

    def __init__(self, x, y, e_type, has_item=False):
        spd = 1.6
        hp = 1
        col = "#888888"
        if e_type == EnemyTank.FAST:
            spd = 2.8
            col = "#f1c40f"
        elif e_type == EnemyTank.POWER:
            spd = 2.0
            col = "#3498db"
        elif e_type == EnemyTank.ARMOR:
            spd = 1.3
            hp = 4
            col = "#27ae60"

        super().__init__(x, y, DIR_DOWN, spd, col)
        self.type = e_type
        self.hp = hp
        self.has_item = has_item
        self.dir_timer = random.randint(30, 80)
        self.shoot_timer = random.randint(40, 90)

    def update_ai(self, game_map, bullets):
        self.dir_timer -= 1
        self.shoot_timer -= 1

        if self.dir_timer <= 0:
            self.dir_timer = random.randint(40, 100)
            if random.random() < 0.45:
                self.dir = DIR_DOWN
            else:
                self.dir = random.choice([DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT])

        nx, ny = self.x, self.y
        if self.dir == DIR_UP:
            ny -= self.speed
        elif self.dir == DIR_DOWN:
            ny += self.speed
        elif self.dir == DIR_LEFT:
            nx -= self.speed
        elif self.dir == DIR_RIGHT:
            nx += self.speed

        if self.can_move(nx, ny, game_map):
            self.x = nx
            self.y = ny
        else:
            self.dir = random.choice([DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT])
            self.dir_timer = random.randint(20, 50)

        if self.shoot_timer <= 0:
            self.shoot_timer = random.randint(50, 110)
            b_spd = 5.5 if self.type == EnemyTank.POWER else 3.8
            cx = self.x + self.size / 2
            cy = self.y + self.size / 2
            bx, by = cx, cy
            if self.dir == DIR_UP:
                by = self.y - 2
            elif self.dir == DIR_DOWN:
                by = self.y + self.size + 2
            elif self.dir == DIR_LEFT:
                bx = self.x - 2
            elif self.dir == DIR_RIGHT:
                bx = self.x + self.size + 2
            bullets.append(Bullet(bx, by, self.dir, b_spd, False, self))

# ================= 游戏主界面 GUI =================
class TankGameApp:
    def __init__(self, root):
        self.root = root
        self.root.title("经典坦克大战 1990 - 典藏桌面版")
        self.root.resizable(False, False)
        self.root.configure(bg="#22222b")

        # 键盘状态记录
        self.keys = {}

        # 游戏状态
        self.is_paused = False
        self.is_game_over = False
        self.is_victory = False
        self.stage = 1
        self.freeze_timer = 0
        self.shovel_timer = 0
        self.remaining_enemies = 20

        self.bullets = []
        self.explosions = []
        self.power_ups = []
        self.enemies = []

        self.init_map()
        self.player = PlayerTank(8 * CELL_SIZE, 24 * CELL_SIZE)

        # 布局
        self.setup_ui()

        # 绑定按键
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)

        # 启动主定时循环 (~60FPS)
        self.game_loop()

    def init_map(self):
        self.map = []
        for row_str in MAP_PRESET:
            row = [int(ch) for ch in row_str]
            self.map.append(row)
        self.base_alive = True

    def setup_ui(self):
        # 整体横向容器
        container = tk.Frame(self.root, bg="#22222b", padx=12, pady=12)
        container.pack()

        # 战场 Canvas
        self.canvas = tk.Canvas(container, width=BOARD_SIZE, height=BOARD_SIZE, bg="#000000", highlightthickness=3, highlightbackground="#555")
        self.canvas.grid(row=0, column=0, rowspan=2)

        # 右侧信息侧边栏
        sidebar = tk.Frame(container, bg="#33333d", width=200, padx=12, pady=12, relief="ridge", bd=2)
        sidebar.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        # 标题
        lbl_title = tk.Label(sidebar, text="坦克大战\n1990", font=("Microsoft YaHei", 18, "bold"), fg="#ffbe0b", bg="#33333d")
        lbl_title.pack(pady=(0, 15))

        # 关卡
        self.lbl_stage = tk.Label(sidebar, text="关卡: 1", font=("Microsoft YaHei", 14, "bold"), fg="#fff", bg="#33333d")
        self.lbl_stage.pack(anchor="w", pady=4)

        # 敌方剩余
        self.lbl_enemies = tk.Label(sidebar, text="敌军剩余: 20", font=("Microsoft YaHei", 12), fg="#e74c3c", bg="#33333d")
        self.lbl_enemies.pack(anchor="w", pady=4)

        # 分割线
        tk.Frame(sidebar, height=2, bg="#555").pack(fill="x", pady=10)

        # 玩家状态
        self.lbl_lives = tk.Label(sidebar, text="❤ 生命: 3", font=("Microsoft YaHei", 13, "bold"), fg="#2ecc71", bg="#33333d")
        self.lbl_lives.pack(anchor="w", pady=4)

        self.lbl_score = tk.Label(sidebar, text="🏆 分数: 0", font=("Microsoft YaHei", 12), fg="#f1c40f", bg="#33333d")
        self.lbl_score.pack(anchor="w", pady=4)

        self.lbl_level = tk.Label(sidebar, text="★ 等级: 1", font=("Microsoft YaHei", 12), fg="#3498db", bg="#33333d")
        self.lbl_level.pack(anchor="w", pady=4)

        # 分割线
        tk.Frame(sidebar, height=2, bg="#555").pack(fill="x", pady=10)

        # 操作提示
        help_text = "操作说明:\n• WASD / 方向键: 移动\n• J / 空格键: 开火\n• P 键: 暂停 / 继续\n• R 键: 重新开始"
        lbl_help = tk.Label(sidebar, text=help_text, font=("Microsoft YaHei", 9), fg="#bbb", bg="#33333d", justify="left")
        lbl_help.pack(anchor="w", pady=(0, 15))

        # 快捷按钮
        btn_frame = tk.Frame(sidebar, bg="#33333d")
        btn_frame.pack(fill="x")

        btn_pause = tk.Button(btn_frame, text="暂停/继续", font=("Microsoft YaHei", 9), bg="#444", fg="#fff", command=self.toggle_pause)
        btn_pause.pack(fill="x", pady=2)

        btn_restart = tk.Button(btn_frame, text="重新开始", font=("Microsoft YaHei", 9), bg="#c0392b", fg="#fff", command=self.restart_game)
        btn_restart.pack(fill="x", pady=2)

    def on_key_press(self, event):
        k = event.keysym.lower()
        self.keys[k] = True
        if k == 'p':
            self.toggle_pause()
        elif k == 'r':
            self.restart_game()

    def on_key_release(self, event):
        k = event.keysym.lower()
        self.keys[k] = False

    def toggle_pause(self):
        self.is_paused = not self.is_paused

    def restart_game(self):
        self.is_game_over = False
        self.is_victory = False
        self.is_paused = False
        self.remaining_enemies = 20
        self.freeze_timer = 0
        self.shovel_timer = 0
        self.init_map()
        self.player = PlayerTank(8 * CELL_SIZE, 24 * CELL_SIZE)
        self.enemies.clear()
        self.bullets.clear()
        self.explosions.clear()
        self.power_ups.clear()
        self.update_sidebar()

    def set_shovel_protection(self, tile_type):
        pos_list = [
            (23, 11), (23, 12), (23, 13), (23, 14),
            (24, 11), (24, 14),
            (25, 11), (25, 14)
        ]
        for r, c in pos_list:
            if 0 <= r < GRID_ROWS and 0 <= c < GRID_COLS:
                self.map[r][c] = tile_type

    def spawn_enemy(self):
        if self.remaining_enemies <= 0 or len(self.enemies) >= 4 or self.freeze_timer > 0:
            return
        spawn_points = [(1 * CELL_SIZE, 1 * CELL_SIZE), (12 * CELL_SIZE, 1 * CELL_SIZE), (23 * CELL_SIZE, 1 * CELL_SIZE)]
        pt = random.choice(spawn_points)
        for e in self.enemies:
            if math.hypot(e.x - pt[0], e.y - pt[1]) < 32:
                return  # 有阻挡
        r = random.random()
        t = EnemyTank.BASIC
        if r < 0.25:
            t = EnemyTank.FAST
        elif r < 0.5:
            t = EnemyTank.POWER
        elif r < 0.8:
            t = EnemyTank.ARMOR
        has_item = random.random() < 0.25
        self.enemies.append(EnemyTank(pt[0], pt[1], t, has_item))
        self.remaining_enemies -= 1
        self.update_sidebar()

    def apply_powerup(self, p_type):
        if p_type == PowerUp.STAR:
            if self.player.level < 3:
                self.player.level += 1
        elif p_type == PowerUp.BOMB:
            for e in self.enemies:
                self.explosions.append(Explosion(e.x + e.size/2, e.y + e.size/2, True))
                self.player.score += 200
            self.enemies.clear()
        elif p_type == PowerUp.CLOCK:
            self.freeze_timer = 250
        elif p_type == PowerUp.SHOVEL:
            self.set_shovel_protection(T_STEEL)
            self.shovel_timer = 400
        elif p_type == PowerUp.HELMET:
            self.player.shield_timer = 300
        elif p_type == PowerUp.TANK:
            self.player.lives += 1
        self.update_sidebar()

    def update_sidebar(self):
        self.lbl_stage.config(text=f"关卡: {self.stage}")
        total_e = self.remaining_enemies + len(self.enemies)
        self.lbl_enemies.config(text=f"敌军剩余: {total_e}")
        self.lbl_lives.config(text=f"❤ 生命: {self.player.lives}")
        self.lbl_score.config(text=f"🏆 分数: {self.player.score}")
        self.lbl_level.config(text=f"★ 等级: {self.player.level + 1}")

    def update_game(self):
        if self.is_paused or self.is_game_over:
            return

        # 铁锹时间
        if self.shovel_timer > 0:
            self.shovel_timer -= 1
            if self.shovel_timer == 0:
                self.set_shovel_protection(T_BRICK)

        # 冻结时间
        if self.freeze_timer > 0:
            self.freeze_timer -= 1

        # 玩家护盾与CD
        if self.player.shield_timer > 0:
            self.player.shield_timer -= 1
        if self.player.shoot_cd > 0:
            self.player.shoot_cd -= 1

        # 玩家移动输入
        dx, dy = 0, 0
        if self.keys.get('w') or self.keys.get('up'):
            self.player.dir = DIR_UP
            dy -= self.player.speed
        elif self.keys.get('s') or self.keys.get('down'):
            self.player.dir = DIR_DOWN
            dy += self.player.speed
        elif self.keys.get('a') or self.keys.get('left'):
            self.player.dir = DIR_LEFT
            dx -= self.player.speed
        elif self.keys.get('d') or self.keys.get('right'):
            self.player.dir = DIR_RIGHT
            dx += self.player.speed

        if dx != 0 or dy != 0:
            nx = self.player.x + dx
            ny = self.player.y + dy
            if self.player.can_move(nx, ny, self.map):
                self.player.x = nx
                self.player.y = ny

        # 玩家射击输入
        if self.keys.get('j') or self.keys.get('space'):
            self.player.shoot(self.bullets)

        # 道具收集
        for p in self.power_ups[:]:
            if (self.player.x < p.x + p.size and self.player.x + self.player.size > p.x and
                self.player.y < p.y + p.size and self.player.y + self.player.size > p.y):
                self.apply_powerup(p.type)
                self.power_ups.remove(p)

        # 敌人更新与刷新
        if random.randint(1, 80) == 1:
            self.spawn_enemy()

        if self.freeze_timer <= 0:
            for e in self.enemies:
                e.update_ai(self.map, self.bullets)

        # 炮弹更新
        for b in self.bullets[:]:
            b.update()
            if not b.active:
                self.bullets.remove(b)
                continue

            # 炮弹与地图碰撞
            col = int(b.x // CELL_SIZE)
            row = int(b.y // CELL_SIZE)
            if 0 <= row < GRID_ROWS and 0 <= col < GRID_COLS:
                t = self.map[row][col]
                if t == T_BRICK:
                    self.map[row][col] = T_EMPTY
                    b.active = False
                    self.explosions.append(Explosion(b.x, b.y, False))
                elif t == T_STEEL:
                    if b.break_steel:
                        self.map[row][col] = T_EMPTY
                    b.active = False
                    self.explosions.append(Explosion(b.x, b.y, False))
                elif t == T_BASE:
                    if self.base_alive:
                        self.base_alive = False
                        b.active = False
                        self.explosions.append(Explosion(12 * CELL_SIZE + 20, 24 * CELL_SIZE + 20, True))
                        self.is_game_over = True

            # 炮弹与敌坦克碰撞
            if b.is_player and b.active:
                for e in self.enemies[:]:
                    if (e.x < b.x < e.x + e.size) and (e.y < b.y < e.y + e.size):
                        b.active = False
                        e.hp -= 1
                        if e.hp <= 0:
                            if e.has_item:
                                p_type = random.choice([PowerUp.STAR, PowerUp.BOMB, PowerUp.CLOCK, PowerUp.SHOVEL, PowerUp.HELMET, PowerUp.TANK])
                                self.power_ups.append(PowerUp(e.x, e.y, p_type))
                            self.enemies.remove(e)
                            self.explosions.append(Explosion(e.x + e.size/2, e.y + e.size/2, True))
                            self.player.score += e.type * 100
                            self.update_sidebar()
                        else:
                            self.explosions.append(Explosion(b.x, b.y, False))
                        break

            # 炮弹与玩家碰撞
            if not b.is_player and b.active:
                p = self.player
                if (p.x < b.x < p.x + p.size) and (p.y < b.y < p.y + p.size):
                    b.active = False
                    if p.shield_timer <= 0:
                        p.lives -= 1
                        self.explosions.append(Explosion(p.x + p.size/2, p.y + p.size/2, True))
                        self.update_sidebar()
                        if p.lives > 0:
                            p.respawn()
                        else:
                            self.is_game_over = True
                    else:
                        self.explosions.append(Explosion(b.x, b.y, False))

        # 更新爆炸动效
        for ex in self.explosions[:]:
            ex.update()
            if ex.is_finished():
                self.explosions.remove(ex)

        # 更新道具时间
        for pu in self.power_ups[:]:
            pu.update()
            if pu.timer <= 0:
                self.power_ups.remove(pu)

    def draw_game(self):
        self.canvas.delete("all")

        # 1. 绘制地图瓦片
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                t = self.map[r][c]
                px = c * CELL_SIZE
                py = r * CELL_SIZE
                if t == T_BRICK:
                    self.canvas.create_rectangle(px, py, px + CELL_SIZE, py + CELL_SIZE, fill="#b33918", outline="#2b1d0c")
                    self.canvas.create_line(px + 2, py + 2, px + CELL_SIZE - 2, py + 2, fill="#d35400")
                elif t == T_STEEL:
                    self.canvas.create_rectangle(px, py, px + CELL_SIZE, py + CELL_SIZE, fill="#bdc3c7", outline="#7f8c8d")
                    self.canvas.create_rectangle(px + 3, py + 3, px + CELL_SIZE - 3, py + CELL_SIZE - 3, fill="#ecf0f1", outline="")
                elif t == T_WATER:
                    self.canvas.create_rectangle(px, py, px + CELL_SIZE, py + CELL_SIZE, fill="#2980b9", outline="")
                    self.canvas.create_line(px, py + 6, px + CELL_SIZE, py + 6, fill="#3498db")

        # 2. 绘制基地
        bx = 12 * CELL_SIZE
        by = 24 * CELL_SIZE
        if self.base_alive:
            self.canvas.create_rectangle(bx + 4, by + 4, bx + 36, by + 36, fill="#f39c12", outline="#d35400")
            self.canvas.create_oval(bx + 12, by + 12, bx + 28, by + 28, fill="#f1c40f", outline="")
            self.canvas.create_text(bx + 20, by + 20, text="🦅", font=("Arial", 16))
        else:
            self.canvas.create_rectangle(bx + 4, by + 4, bx + 36, by + 36, fill="#444", outline="#222")
            self.canvas.create_text(bx + 20, by + 20, text="💀", font=("Arial", 16))

        # 3. 绘制道具
        for pu in self.power_ups:
            icons = {PowerUp.STAR: "★", PowerUp.BOMB: "💣", PowerUp.CLOCK: "⏱",
                     PowerUp.SHOVEL: "⛏", PowerUp.HELMET: "🛡", PowerUp.TANK: "❤"}
            self.canvas.create_rectangle(pu.x, pu.y, pu.x + pu.size, pu.y + pu.size, fill="#111", outline="#fff", width=2)
            self.canvas.create_text(pu.x + pu.size/2, pu.y + pu.size/2, text=icons.get(pu.type, "?"), fill="#ffbe0b", font=("Arial", 12, "bold"))

        # 4. 绘制敌方坦克
        for e in self.enemies:
            self.draw_tank(e.x, e.y, e.size, e.dir, e.color)

        # 5. 绘制玩家坦克
        if self.player.lives > 0:
            p_col = "#e5a93b" if self.player.level < 2 else "#27ae60"
            self.draw_tank(self.player.x, self.player.y, self.player.size, self.player.dir, p_col)
            # 无敌护盾光环
            if self.player.shield_timer > 0:
                cx = self.player.x + self.player.size / 2
                cy = self.player.y + self.player.size / 2
                self.canvas.create_oval(cx - 18, cy - 18, cx + 18, cy + 18, outline="#00ffff", width=2)

        # 6. 绘制草丛 (遮盖在坦克上方)
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                if self.map[r][c] == T_GRASS:
                    px = c * CELL_SIZE
                    py = r * CELL_SIZE
                    self.canvas.create_rectangle(px, py, px + CELL_SIZE, py + CELL_SIZE, fill="#27ae60", outline="")
                    self.canvas.create_oval(px + 4, py + 4, px + 10, py + 10, fill="#2ecc71", outline="")

        # 7. 绘制炮弹
        for b in self.bullets:
            col = "#ffea00" if b.is_player else "#ffffff"
            self.canvas.create_oval(b.x - 3, b.y - 3, b.x + 3, b.y + 3, fill=col, outline="")

        # 8. 绘制爆炸
        for ex in self.explosions:
            rad = (26 if ex.is_big else 12) * (1 - ex.frame / ex.max_frames)
            col = "#f1c40f" if ex.frame < ex.max_frames / 2 else "#e74c3c"
            self.canvas.create_oval(ex.x - rad, ex.y - rad, ex.x + rad, ex.y + rad, fill=col, outline="")

        # 9. 状态覆盖提示 (Game Over / Pause)
        if self.is_game_over:
            self.canvas.create_text(BOARD_SIZE / 2, BOARD_SIZE / 2, text="GAME OVER", font=("Microsoft YaHei", 36, "bold"), fill="#e74c3c")
            self.canvas.create_text(BOARD_SIZE / 2, BOARD_SIZE / 2 + 45, text="按 R 键重新开始", font=("Microsoft YaHei", 14), fill="#fff")
        elif self.is_paused:
            self.canvas.create_text(BOARD_SIZE / 2, BOARD_SIZE / 2, text="PAUSED", font=("Microsoft YaHei", 36, "bold"), fill="#f1c40f")

    def draw_tank(self, x, y, size, direction, color):
        cx = x + size / 2
        cy = y + size / 2
        # 履带与车身
        if direction in (DIR_UP, DIR_DOWN):
            self.canvas.create_rectangle(x, y, x + 6, y + size, fill="#111", outline="")
            self.canvas.create_rectangle(x + size - 6, y, x + size, y + size, fill="#111", outline="")
            self.canvas.create_rectangle(x + 5, y + 3, x + size - 5, y + size - 3, fill=color, outline="#222")
            # 炮塔
            self.canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill="#333", outline="")
            # 炮管
            if direction == DIR_UP:
                self.canvas.create_line(cx, cy, cx, y - 4, fill="#fff", width=3)
            else:
                self.canvas.create_line(cx, cy, cx, y + size + 4, fill="#fff", width=3)
        else:
            self.canvas.create_rectangle(x, y, x + size, y + 6, fill="#111", outline="")
            self.canvas.create_rectangle(x, y + size - 6, x + size, y + size, fill="#111", outline="")
            self.canvas.create_rectangle(x + 3, y + 5, x + size - 3, y + size - 5, fill=color, outline="#222")
            # 炮塔
            self.canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill="#333", outline="")
            # 炮管
            if direction == DIR_LEFT:
                self.canvas.create_line(cx, cy, x - 4, cy, fill="#fff", width=3)
            else:
                self.canvas.create_line(cx, cy, x + size + 4, cy, fill="#fff", width=3)

    def game_loop(self):
        self.update_game()
        self.draw_game()
        self.root.after(20, self.game_loop)  # 50 FPS 循环

if __name__ == '__main__':
    root = tk.Tk()
    app = TankGameApp(root)
    root.mainloop()
