# -*- coding: utf-8 -*-
"""
生成精美原生的俄罗斯方块（Tetris）单文件小游戏至用户桌面
包含：Web Audio 原生合成音效、粒子爆炸特效、Ghost 投影、Hold 暂存、Next 预览、等级递增、键盘与虚拟按键双控
"""
import os
import sys

HTML_CONTENT = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>经典霓虹俄罗斯方块 | Cyber Tetris</title>
  <style>
    :root {
      --bg-dark: #0a0e17;
      --bg-panel: rgba(18, 24, 38, 0.78);
      --border-panel: rgba(56, 189, 248, 0.25);
      --border-glow: rgba(56, 189, 248, 0.5);
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --cyan: #06b6d4;
      --sky: #38bdf8;
      --purple: #a855f7;
      --yellow: #eab308;
      --green: #22c55e;
      --red: #ef4444;
      --orange: #f97316;
      --blue: #3b82f6;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      user-select: none;
      -webkit-user-select: none;
    }

    body {
      background: radial-gradient(circle at 50% 20%, #151e33 0%, #080c14 75%, #03060a 100%);
      color: var(--text-main);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      overflow-x: hidden;
      padding: 16px;
    }

    /* 顶部标题区 */
    .header-bar {
      text-align: center;
      margin-bottom: 14px;
    }
    .header-bar h1 {
      font-size: 2.1rem;
      font-weight: 900;
      letter-spacing: 3px;
      text-transform: uppercase;
      background: linear-gradient(135deg, #38bdf8 0%, #a855f7 50%, #ec4899 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      filter: drop-shadow(0 2px 12px rgba(168, 85, 247, 0.35));
    }
    .header-bar .subtitle {
      font-size: 0.85rem;
      color: var(--text-muted);
      letter-spacing: 1px;
      margin-top: 2px;
    }

    /* 游戏主舞台布局 */
    .game-container {
      display: flex;
      gap: 20px;
      align-items: flex-start;
      justify-content: center;
      position: relative;
    }

    /* 侧边信息栏 */
    .side-column {
      display: flex;
      flex-direction: column;
      gap: 14px;
      width: 140px;
    }

    .panel-card {
      background: var(--bg-panel);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid var(--border-panel);
      border-radius: 14px;
      padding: 14px 12px;
      text-align: center;
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.1);
      transition: border-color 0.25s, box-shadow 0.25s;
    }
    .panel-card:hover {
      border-color: var(--border-glow);
      box-shadow: 0 10px 35px rgba(56, 189, 248, 0.18);
    }
    .panel-title {
      font-size: 0.75rem;
      font-weight: 700;
      color: var(--sky);
      letter-spacing: 1.5px;
      text-transform: uppercase;
      margin-bottom: 8px;
    }
    .stat-value {
      font-size: 1.5rem;
      font-weight: 800;
      font-family: "JetBrains Mono", Consolas, monospace;
      color: #fff;
      text-shadow: 0 0 12px rgba(56, 189, 248, 0.6);
    }

    .mini-canvas {
      display: block;
      margin: 0 auto;
      border-radius: 8px;
      background: rgba(8, 12, 20, 0.8);
      border: 1px solid rgba(255, 255, 255, 0.05);
    }

    /* 主画布外壳 */
    .board-wrapper {
      position: relative;
      background: rgba(10, 15, 26, 0.92);
      border: 2px solid var(--border-panel);
      border-radius: 16px;
      padding: 6px;
      box-shadow: 0 15px 45px rgba(0, 0, 0, 0.6), 0 0 30px rgba(56, 189, 248, 0.15);
    }
    #game-canvas {
      display: block;
      border-radius: 10px;
      background: #060911;
    }

    /* 浮层状态遮罩 (暂停/游戏结束) */
    .overlay-modal {
      position: absolute;
      top: 6px;
      left: 6px;
      right: 6px;
      bottom: 6px;
      border-radius: 10px;
      background: rgba(6, 9, 17, 0.88);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 16px;
      z-index: 20;
      transition: opacity 0.25s;
    }
    .overlay-modal.hidden {
      display: none;
    }
    .overlay-title {
      font-size: 2rem;
      font-weight: 900;
      letter-spacing: 2px;
      color: #fff;
      text-shadow: 0 0 18px rgba(239, 68, 68, 0.6);
    }
    .overlay-desc {
      font-size: 0.95rem;
      color: var(--text-muted);
    }
    .btn-action {
      background: linear-gradient(135deg, #0284c7 0%, #6366f1 100%);
      color: #fff;
      border: none;
      padding: 10px 26px;
      font-size: 1rem;
      font-weight: 700;
      border-radius: 30px;
      cursor: pointer;
      box-shadow: 0 4px 18px rgba(99, 102, 241, 0.45);
      transition: transform 0.15s, box-shadow 0.15s;
    }
    .btn-action:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 24px rgba(99, 102, 241, 0.65);
    }
    .btn-action:active {
      transform: translateY(1px);
    }

    /* 控制说明与快捷按钮 */
    .ctrl-hints {
      margin-top: 18px;
      background: var(--bg-panel);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      padding: 10px 20px;
      max-width: 620px;
      display: flex;
      flex-wrap: wrap;
      gap: 14px 24px;
      justify-content: center;
      font-size: 0.82rem;
      color: var(--text-muted);
    }
    .hint-item {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .key-badge {
      display: inline-block;
      padding: 2px 7px;
      font-size: 0.75rem;
      font-family: monospace;
      font-weight: 700;
      color: #fff;
      background: rgba(255, 255, 255, 0.12);
      border: 1px solid rgba(255, 255, 255, 0.2);
      border-radius: 5px;
      box-shadow: 0 2px 0 rgba(0,0,0,0.4);
    }

    /* 虚拟移动触控板 (支持屏幕点击) */
    .touch-controls {
      margin-top: 14px;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
      width: 100%;
      max-width: 440px;
    }
    .touch-btn {
      background: rgba(30, 41, 59, 0.7);
      border: 1px solid rgba(255, 255, 255, 0.1);
      color: #fff;
      padding: 12px 0;
      border-radius: 10px;
      font-size: 0.95rem;
      font-weight: 700;
      cursor: pointer;
      touch-action: manipulation;
      transition: background 0.1s, transform 0.1s;
    }
    .touch-btn:active {
      background: rgba(56, 189, 248, 0.25);
      transform: scale(0.96);
      border-color: var(--sky);
    }
    .touch-btn.highlight {
      background: rgba(99, 102, 241, 0.4);
      border-color: rgba(99, 102, 241, 0.6);
    }

    /* 顶部音效切换 */
    .top-toolbar {
      position: absolute;
      top: 16px;
      right: 20px;
      display: flex;
      gap: 10px;
    }
    .icon-btn {
      background: rgba(18, 24, 38, 0.8);
      border: 1px solid var(--border-panel);
      color: var(--text-main);
      width: 38px;
      height: 38px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 1.1rem;
      transition: all 0.2s;
    }
    .icon-btn:hover {
      border-color: var(--sky);
      transform: scale(1.08);
    }

    /* 浮动消行 Combo 消息 */
    .combo-toast {
      position: absolute;
      top: 25%;
      left: 50%;
      transform: translate(-50%, -50%) scale(0.6);
      font-size: 2rem;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 2px;
      pointer-events: none;
      opacity: 0;
      z-index: 30;
      transition: transform 0.3s cubic-bezier(0.18, 0.89, 0.32, 1.28), opacity 0.3s ease;
      text-shadow: 0 0 25px currentColor;
    }
    .combo-toast.show {
      transform: translate(-50%, -50%) scale(1.15);
      opacity: 1;
    }

    @media (max-width: 680px) {
      .game-container {
        flex-direction: column;
        align-items: center;
      }
      .side-column {
        flex-direction: row;
        width: 100%;
        max-width: 330px;
        justify-content: space-between;
      }
      .panel-card {
        flex: 1;
        padding: 8px 6px;
      }
      .stat-value {
        font-size: 1.1rem;
      }
      .header-bar h1 {
        font-size: 1.6rem;
      }
      .ctrl-hints {
        display: none;
      }
      .top-toolbar {
        position: static;
        margin-bottom: 8px;
      }
    }
  </style>
</head>
<body>

  <!-- 顶部工具栏 -->
  <div class="top-toolbar">
    <button class="icon-btn" id="sound-btn" title="开关音效">🔊</button>
    <button class="icon-btn" id="pause-btn" title="暂停/继续">⏸️</button>
    <button class="icon-btn" id="restart-btn" title="重新开始">🔄</button>
  </div>

  <!-- 标题 -->
  <div class="header-bar">
    <h1>TETRIS</h1>
    <div class="subtitle">CYBER ELECTRIC EDITION</div>
  </div>

  <!-- 游戏主舞台 -->
  <div class="game-container">
    
    <!-- 左侧信息栏: 暂存 HOLD & 分数 SCORE -->
    <div class="side-column">
      <div class="panel-card">
        <div class="panel-title">暂存 HOLD</div>
        <canvas id="hold-canvas" class="mini-canvas" width="100" height="100"></canvas>
      </div>

      <div class="panel-card">
        <div class="panel-title">得分 SCORE</div>
        <div class="stat-value" id="score-val">0</div>
      </div>

      <div class="panel-card">
        <div class="panel-title">消除 LINES</div>
        <div class="stat-value" id="lines-val">0</div>
      </div>
    </div>

    <!-- 中间主战场 -->
    <div class="board-wrapper">
      <canvas id="game-canvas" width="300" height="600"></canvas>
      
      <!-- 消除浮动特效 -->
      <div id="combo-toast" class="combo-toast">TETRIS!</div>

      <!-- 游戏结束/暂停遮罩层 -->
      <div id="overlay" class="overlay-modal hidden">
        <div class="overlay-title" id="overlay-title">GAME OVER</div>
        <div class="overlay-desc" id="overlay-desc">最终得分: 0</div>
        <button class="btn-action" id="overlay-action-btn">再来一局</button>
      </div>
    </div>

    <!-- 右侧信息栏: 下一个 NEXT & 等级 LEVEL -->
    <div class="side-column">
      <div class="panel-card">
        <div class="panel-title">下一个 NEXT</div>
        <canvas id="next-canvas" class="mini-canvas" width="100" height="100"></canvas>
      </div>

      <div class="panel-card">
        <div class="panel-title">等级 LEVEL</div>
        <div class="stat-value" id="level-val">1</div>
      </div>

      <div class="panel-card">
        <div class="panel-title">最高分 BEST</div>
        <div class="stat-value" id="high-val">0</div>
      </div>
    </div>

  </div>

  <!-- 键盘提示 -->
  <div class="ctrl-hints">
    <div class="hint-item"><span class="key-badge">←</span> <span class="key-badge">→</span> 左右平移</div>
    <div class="hint-item"><span class="key-badge">↑</span> 或 <span class="key-badge">W</span> 旋转方块</div>
    <div class="hint-item"><span class="key-badge">↓</span> 或 <span class="key-badge">S</span> 软加速下落</div>
    <div class="hint-item"><span class="key-badge">SPACE 空格</span> 瞬间硬着陆</div>
    <div class="hint-item"><span class="key-badge">C</span> 或 <span class="key-badge">Shift</span> 暂存方块</div>
    <div class="hint-item"><span class="key-badge">P</span> 暂停游戏</div>
  </div>

  <!-- 屏幕触控/鼠标快速控制按钮 -->
  <div class="touch-controls">
    <button class="touch-btn" id="btn-left">← 左移</button>
    <button class="touch-btn highlight" id="btn-rotate">↻ 旋转</button>
    <button class="touch-btn" id="btn-right">右移 →</button>
    <button class="touch-btn" id="btn-hold">暂存 C</button>
    <button class="touch-btn" id="btn-down" style="grid-column: span 2;">↓ 软下落</button>
    <button class="touch-btn highlight" id="btn-drop" style="grid-column: span 2;">⚡ 瞬间降落</button>
  </div>

  <script>
    /* ========================================================
       1. 音频合成引擎 (Web Audio API - 原生免素材)
       ======================================================== */
    class SoundEngine {
      constructor() {
        this.ctx = null;
        this.enabled = true;
      }

      init() {
        if (!this.ctx) {
          const AudioContext = window.AudioContext || window.webkitAudioContext;
          if (AudioContext) {
            this.ctx = new AudioContext();
          }
        }
        if (this.ctx && this.ctx.state === 'suspended') {
          this.ctx.resume();
        }
      }

      playTone(freq, duration, type = 'sine', gainVal = 0.15) {
        if (!this.enabled) return;
        this.init();
        if (!this.ctx) return;

        try {
          const osc = this.ctx.createOscillator();
          const gain = this.ctx.createGain();
          osc.type = type;
          osc.frequency.setValueAtTime(freq, this.ctx.currentTime);

          gain.gain.setValueAtTime(gainVal, this.ctx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);

          osc.connect(gain);
          gain.connect(this.ctx.destination);

          osc.start();
          osc.stop(this.ctx.currentTime + duration);
        } catch(e) {}
      }

      move() { this.playTone(260, 0.05, 'triangle', 0.08); }
      rotate() { this.playTone(420, 0.08, 'sine', 0.12); }
      hold() { this.playTone(330, 0.12, 'square', 0.08); }
      hardDrop() { this.playTone(140, 0.18, 'sawtooth', 0.2); }
      
      clearLine(lines) {
        if (!this.enabled) return;
        const freqs = [523.25, 659.25, 783.99, 1046.50];
        lines = Math.min(lines, 4);
        for (let i = 0; i < lines; i++) {
          setTimeout(() => {
            this.playTone(freqs[i] || 880, 0.18, 'sine', 0.18);
          }, i * 65);
        }
      }

      tetrisCombo() {
        if (!this.enabled) return;
        [523.25, 659.25, 783.99, 1046.50, 1318.51].forEach((f, i) => {
          setTimeout(() => this.playTone(f, 0.22, 'triangle', 0.22), i * 60);
        });
      }

      gameOver() {
        if (!this.enabled) return;
        [320, 280, 240, 180].forEach((f, i) => {
          setTimeout(() => this.playTone(f, 0.28, 'sawtooth', 0.2), i * 90);
        });
      }
    }

    const sound = new SoundEngine();

    /* ========================================================
       2. 方块定义与七种经典形状 (SRS 颜色标准)
       ======================================================== */
    const COLS = 10;
    const ROWS = 20;
    const BLOCK_SIZE = 30; // 300x600

    const SHAPES = {
      I: [
        [0, 0, 0, 0],
        [1, 1, 1, 1],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
      ],
      J: [
        [1, 0, 0],
        [1, 1, 1],
        [0, 0, 0]
      ],
      L: [
        [0, 0, 1],
        [1, 1, 1],
        [0, 0, 0]
      ],
      O: [
        [1, 1],
        [1, 1]
      ],
      S: [
        [0, 1, 1],
        [1, 1, 0],
        [0, 0, 0]
      ],
      T: [
        [0, 1, 0],
        [1, 1, 1],
        [0, 0, 0]
      ],
      Z: [
        [1, 1, 0],
        [0, 1, 1],
        [0, 0, 0]
      ]
    };

    const PIECE_COLORS = {
      I: { primary: '#06b6d4', glow: 'rgba(6, 182, 212, 0.65)', light: '#67e8f9' },
      J: { primary: '#3b82f6', glow: 'rgba(59, 130, 246, 0.65)', light: '#93c5fd' },
      L: { primary: '#f97316', glow: 'rgba(249, 115, 22, 0.65)', light: '#fdba74' },
      O: { primary: '#eab308', glow: 'rgba(234, 179, 8, 0.65)', light: '#fde047' },
      S: { primary: '#22c55e', glow: 'rgba(34, 197, 94, 0.65)', light: '#86efac' },
      T: { primary: '#a855f7', glow: 'rgba(168, 85, 247, 0.65)', light: '#d8b4fe' },
      Z: { primary: '#ef4444', glow: 'rgba(239, 68, 68, 0.65)', light: '#fca5a5' }
    };

    /* ========================================================
       3. 粒子消行爆炸特效系统
       ======================================================== */
    class Particle {
      constructor(x, y, color) {
        this.x = x;
        this.y = y;
        this.color = color;
        this.size = Math.random() * 4 + 2;
        this.vx = (Math.random() - 0.5) * 8;
        this.vy = (Math.random() - 0.5) * 8 - 2;
        this.gravity = 0.25;
        this.alpha = 1;
        this.decay = Math.random() * 0.03 + 0.015;
      }

      update() {
        this.x += this.vx;
        this.y += this.vy;
        this.vy += this.gravity;
        this.alpha -= this.decay;
      }

      draw(ctx) {
        if (this.alpha <= 0) return;
        ctx.save();
        ctx.globalAlpha = Math.max(0, this.alpha);
        ctx.fillStyle = this.color;
        ctx.shadowColor = this.color;
        ctx.shadowBlur = 6;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
    }

    /* ========================================================
       4. 游戏核心状态机
       ======================================================== */
    class TetrisGame {
      constructor() {
        this.canvas = document.getElementById('game-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.nextCanvas = document.getElementById('next-canvas');
        this.nextCtx = this.nextCanvas.getContext('2d');
        this.holdCanvas = document.getElementById('hold-canvas');
        this.holdCtx = this.holdCanvas.getContext('2d');

        this.grid = Array.from({ length: ROWS }, () => Array(COLS).fill(null));
        this.particles = [];

        this.currentPiece = null;
        this.nextPiece = null;
        this.holdPiece = null;
        this.canHold = true;

        this.bag = [];
        this.score = 0;
        this.lines = 0;
        this.level = 1;
        this.highScore = parseInt(localStorage.getItem('tetris_highscore') || '0', 10);

        this.isGameOver = false;
        this.isPaused = false;
        this.dropCounter = 0;
        this.dropInterval = 1000;
        this.lastTime = 0;
        this.animId = null;

        this.initDOM();
        this.initControls();
        this.resetGame();
      }

      initDOM() {
        document.getElementById('high-val').innerText = this.highScore;
        this.updateStats();
      }

      updateStats() {
        document.getElementById('score-val').innerText = this.score;
        document.getElementById('lines-val').innerText = this.lines;
        document.getElementById('level-val').innerText = this.level;
        if (this.score > this.highScore) {
          this.highScore = this.score;
          document.getElementById('high-val').innerText = this.highScore;
          localStorage.setItem('tetris_highscore', this.highScore);
        }
        // 根据等级加速
        this.dropInterval = Math.max(100, 1000 - (this.level - 1) * 85);
      }

      showToast(text, color = '#38bdf8') {
        const toast = document.getElementById('combo-toast');
        toast.innerText = text;
        toast.style.color = color;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 900);
      }

      // 7-Bag 随机算法保证方块分布公平
      generateBag() {
        const keys = Object.keys(SHAPES);
        for (let i = keys.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          [keys[i], keys[j]] = [keys[j], keys[i]];
        }
        return keys;
      }

      getNewPiece() {
        if (this.bag.length === 0) {
          this.bag = this.generateBag();
        }
        const type = this.bag.pop();
        return {
          type,
          matrix: SHAPES[type].map(row => [...row]),
          x: Math.floor(COLS / 2) - Math.ceil(SHAPES[type][0].length / 2),
          y: 0
        };
      }

      resetGame() {
        this.grid = Array.from({ length: ROWS }, () => Array(COLS).fill(null));
        this.particles = [];
        this.bag = [];
        this.score = 0;
        this.lines = 0;
        this.level = 1;
        this.isGameOver = false;
        this.isPaused = false;
        this.holdPiece = null;
        this.canHold = true;
        this.dropCounter = 0;
        this.lastTime = 0;

        this.currentPiece = this.getNewPiece();
        this.nextPiece = this.getNewPiece();

        document.getElementById('overlay').classList.add('hidden');
        this.updateStats();
        this.drawHold();
        this.drawNext();
      }

      /* 碰撞与边界判定 */
      collide(piece, offsetX = 0, offsetY = 0, testMatrix = null) {
        const matrix = testMatrix || piece.matrix;
        for (let r = 0; r < matrix.length; r++) {
          for (let c = 0; c < matrix[r].length; c++) {
            if (matrix[r][c]) {
              const newX = piece.x + c + offsetX;
              const newY = piece.y + r + offsetY;
              if (newX < 0 || newX >= COLS || newY >= ROWS) {
                return true;
              }
              if (newY >= 0 && this.grid[newY][newX]) {
                return true;
              }
            }
          }
        }
        return false;
      }

      /* 顺时针旋转矩阵 */
      rotateMatrix(matrix) {
        const N = matrix.length;
        const result = Array.from({ length: N }, () => Array(N).fill(0));
        for (let r = 0; r < N; r++) {
          for (let c = 0; c < N; c++) {
            result[c][N - 1 - r] = matrix[r][c];
          }
        }
        return result;
      }

      rotate() {
        if (this.isGameOver || this.isPaused) return;
        const rotated = this.rotateMatrix(this.currentPiece.matrix);
        // Wall kick 踢墙偏移探测: 0, -1, 1, -2, 2
        const kicks = [0, -1, 1, -2, 2];
        for (let kick of kicks) {
          if (!this.collide(this.currentPiece, kick, 0, rotated)) {
            this.currentPiece.x += kick;
            this.currentPiece.matrix = rotated;
            sound.rotate();
            return;
          }
        }
      }

      move(dir) {
        if (this.isGameOver || this.isPaused) return;
        if (!this.collide(this.currentPiece, dir, 0)) {
          this.currentPiece.x += dir;
          sound.move();
        }
      }

      drop() {
        if (this.isGameOver || this.isPaused) return;
        if (!this.collide(this.currentPiece, 0, 1)) {
          this.currentPiece.y++;
          this.dropCounter = 0;
        } else {
          this.lockPiece();
        }
      }

      hardDrop() {
        if (this.isGameOver || this.isPaused) return;
        let dropDistance = 0;
        while (!this.collide(this.currentPiece, 0, 1)) {
          this.currentPiece.y++;
          dropDistance++;
        }
        this.score += dropDistance * 2;
        sound.hardDrop();
        this.lockPiece();
      }

      hold() {
        if (this.isGameOver || this.isPaused || !this.canHold) return;
        sound.hold();
        if (!this.holdPiece) {
          this.holdPiece = this.currentPiece.type;
          this.currentPiece = this.nextPiece;
          this.nextPiece = this.getNewPiece();
          this.drawNext();
        } else {
          const temp = this.holdPiece;
          this.holdPiece = this.currentPiece.type;
          this.currentPiece = {
            type: temp,
            matrix: SHAPES[temp].map(row => [...row]),
            x: Math.floor(COLS / 2) - Math.ceil(SHAPES[temp][0].length / 2),
            y: 0
          };
        }
        this.canHold = false;
        this.drawHold();
      }

      getGhostY() {
        let ghostY = this.currentPiece.y;
        while (!this.collide(this.currentPiece, 0, ghostY - this.currentPiece.y + 1)) {
          ghostY++;
        }
        return ghostY;
      }

      lockPiece() {
        const { matrix, x, y, type } = this.currentPiece;
        for (let r = 0; r < matrix.length; r++) {
          for (let c = 0; c < matrix[r].length; c++) {
            if (matrix[r][c]) {
              const targetY = y + r;
              if (targetY < 0) {
                this.triggerGameOver();
                return;
              }
              this.grid[targetY][x + c] = type;
            }
          }
        }

        this.clearFullLines();
        this.canHold = true;

        this.currentPiece = this.nextPiece;
        this.nextPiece = this.getNewPiece();
        this.drawNext();

        if (this.collide(this.currentPiece)) {
          this.triggerGameOver();
        }
      }

      clearFullLines() {
        let cleared = 0;
        for (let r = ROWS - 1; r >= 0; r--) {
          if (this.grid[r].every(cell => cell !== null)) {
            // 生成消行爆炸粒子
            for (let c = 0; c < COLS; c++) {
              const colorType = this.grid[r][c];
              const pColor = PIECE_COLORS[colorType] ? PIECE_COLORS[colorType].primary : '#fff';
              for (let p = 0; p < 4; p++) {
                this.particles.push(new Particle(
                  c * BLOCK_SIZE + BLOCK_SIZE / 2,
                  r * BLOCK_SIZE + BLOCK_SIZE / 2,
                  pColor
                ));
              }
            }

            this.grid.splice(r, 1);
            this.grid.unshift(Array(COLS).fill(null));
            cleared++;
            r++; // 重新检测当前行
          }
        }

        if (cleared > 0) {
          const linePoints = [0, 100, 300, 500, 800];
          this.score += (linePoints[cleared] || 1000) * this.level;
          this.lines += cleared;
          this.level = Math.floor(this.lines / 10) + 1;

          if (cleared === 4) {
            sound.tetrisCombo();
            this.showToast('TETRIS! +800', '#ec4899');
          } else {
            sound.clearLine(cleared);
            const toasts = ['', 'SINGLE +100', 'DOUBLE +300', 'TRIPLE +500'];
            this.showToast(toasts[cleared] || 'CLEAR!', '#38bdf8');
          }

          this.updateStats();
        }
      }

      triggerGameOver() {
        this.isGameOver = true;
        sound.gameOver();
        document.getElementById('overlay-title').innerText = 'GAME OVER';
        document.getElementById('overlay-desc').innerText = `最终得分: ${this.score}  |  消除: ${this.lines} 行`;
        document.getElementById('overlay-action-btn').innerText = '再玩一次';
        document.getElementById('overlay').classList.remove('hidden');
      }

      togglePause() {
        if (this.isGameOver) return;
        this.isPaused = !this.isPaused;
        const overlay = document.getElementById('overlay');
        const pauseBtn = document.getElementById('pause-btn');

        if (this.isPaused) {
          pauseBtn.innerText = '▶️';
          document.getElementById('overlay-title').innerText = 'PAUSED';
          document.getElementById('overlay-desc').innerText = '游戏已暂停，按 P 或点击继续';
          document.getElementById('overlay-action-btn').innerText = '继续游戏';
          overlay.classList.remove('hidden');
        } else {
          pauseBtn.innerText = '⏸️';
          overlay.classList.add('hidden');
          this.lastTime = performance.now();
        }
      }

      /* 绘图引擎 */
      drawBlock(ctx, x, y, type, alpha = 1, isGhost = false) {
        const color = PIECE_COLORS[type];
        if (!color) return;

        const px = x * BLOCK_SIZE;
        const py = y * BLOCK_SIZE;

        ctx.save();
        ctx.globalAlpha = alpha;

        if (isGhost) {
          ctx.strokeStyle = color.primary;
          ctx.lineWidth = 1.5;
          ctx.strokeRect(px + 1.5, py + 1.5, BLOCK_SIZE - 3, BLOCK_SIZE - 3);
          ctx.fillStyle = color.glow;
          ctx.globalAlpha = 0.15;
          ctx.fillRect(px + 2, py + 2, BLOCK_SIZE - 4, BLOCK_SIZE - 4);
          ctx.restore();
          return;
        }

        // 方块实体渐变与霓虹发光
        const grad = ctx.createLinearGradient(px, py, px + BLOCK_SIZE, py + BLOCK_SIZE);
        grad.addColorStop(0, color.light);
        grad.addColorStop(1, color.primary);

        ctx.fillStyle = grad;
        ctx.shadowColor = color.glow;
        ctx.shadowBlur = 8;
        ctx.fillRect(px + 1, py + 1, BLOCK_SIZE - 2, BLOCK_SIZE - 2);

        // 高光边框
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
        ctx.lineWidth = 1;
        ctx.strokeRect(px + 2, py + 2, BLOCK_SIZE - 4, BLOCK_SIZE - 4);

        ctx.restore();
      }

      drawPreview(ctx, type, canvas) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        if (!type) return;

        const shape = SHAPES[type];
        const rows = shape.length;
        const cols = shape[0].length;
        const miniSize = 20;

        const offsetX = (canvas.width - cols * miniSize) / 2;
        const offsetY = (canvas.height - rows * miniSize) / 2;

        for (let r = 0; r < rows; r++) {
          for (let c = 0; c < cols; c++) {
            if (shape[r][c]) {
              const color = PIECE_COLORS[type];
              ctx.save();
              ctx.fillStyle = color.primary;
              ctx.shadowColor = color.glow;
              ctx.shadowBlur = 6;
              ctx.fillRect(offsetX + c * miniSize + 1, offsetY + r * miniSize + 1, miniSize - 2, miniSize - 2);
              ctx.restore();
            }
          }
        }
      }

      drawHold() {
        this.drawPreview(this.holdCtx, this.holdPiece, this.holdCanvas);
      }

      drawNext() {
        if (this.nextPiece) {
          this.drawPreview(this.nextCtx, this.nextPiece.type, this.nextCanvas);
        }
      }

      drawGrid() {
        // 背景网格线
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.035)';
        this.ctx.lineWidth = 1;
        for (let c = 0; c <= COLS; c++) {
          this.ctx.beginPath();
          this.ctx.moveTo(c * BLOCK_SIZE, 0);
          this.ctx.lineTo(c * BLOCK_SIZE, ROWS * BLOCK_SIZE);
          this.ctx.stroke();
        }
        for (let r = 0; r <= ROWS; r++) {
          this.ctx.beginPath();
          this.ctx.moveTo(0, r * BLOCK_SIZE);
          this.ctx.lineTo(COLS * BLOCK_SIZE, r * BLOCK_SIZE);
          this.ctx.stroke();
        }
      }

      render() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.drawGrid();

        // 绘制棋盘固化方块
        for (let r = 0; r < ROWS; r++) {
          for (let c = 0; c < COLS; c++) {
            if (this.grid[r][c]) {
              this.drawBlock(this.ctx, c, r, this.grid[r][c]);
            }
          }
        }

        // 绘制 Ghost 投影方块
        if (this.currentPiece && !this.isGameOver) {
          const ghostY = this.getGhostY();
          const { matrix, x, type } = this.currentPiece;
          for (let r = 0; r < matrix.length; r++) {
            for (let c = 0; c < matrix[r].length; c++) {
              if (matrix[r][c]) {
                this.drawBlock(this.ctx, x + c, ghostY + r, type, 0.8, true);
              }
            }
          }

          // 绘制当前正在下落方块
          for (let r = 0; r < matrix.length; r++) {
            for (let c = 0; c < matrix[r].length; c++) {
              if (matrix[r][c]) {
                this.drawBlock(this.ctx, x + c, this.currentPiece.y + r, type);
              }
            }
          }
        }

        // 绘制消行粒子
        for (let i = this.particles.length - 1; i >= 0; i--) {
          const p = this.particles[i];
          p.update();
          p.draw(this.ctx);
          if (p.alpha <= 0) {
            this.particles.splice(i, 1);
          }
        }
      }

      update(time = 0) {
        const delta = time - this.lastTime;
        this.lastTime = time;

        if (!this.isPaused && !this.isGameOver) {
          this.dropCounter += delta;
          if (this.dropCounter > this.dropInterval) {
            this.drop();
          }
        }

        this.render();
        this.animId = requestAnimationFrame(this.update.bind(this));
      }

      /* 键盘与触控绑定 */
      initControls() {
        window.addEventListener('keydown', e => {
          // 解锁 AudioContext
          sound.init();

          if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].includes(e.key)) {
            e.preventDefault();
          }

          switch (e.key) {
            case 'ArrowLeft':
            case 'a':
            case 'A':
              this.move(-1);
              break;
            case 'ArrowRight':
            case 'd':
            case 'D':
              this.move(1);
              break;
            case 'ArrowUp':
            case 'w':
            case 'W':
              this.rotate();
              break;
            case 'ArrowDown':
            case 's':
            case 'S':
              this.drop();
              break;
            case ' ':
              this.hardDrop();
              break;
            case 'c':
            case 'C':
            case 'Shift':
              this.hold();
              break;
            case 'p':
            case 'P':
              this.togglePause();
              break;
            case 'r':
            case 'R':
              this.resetGame();
              break;
          }
        });

        // 触控虚拟按钮事件
        const bindBtn = (id, action) => {
          const el = document.getElementById(id);
          if (el) {
            el.addEventListener('click', (e) => {
              e.preventDefault();
              sound.init();
              action();
            });
          }
        };

        bindBtn('btn-left', () => this.move(-1));
        bindBtn('btn-right', () => this.move(1));
        bindBtn('btn-rotate', () => this.rotate());
        bindBtn('btn-down', () => this.drop());
        bindBtn('btn-drop', () => this.hardDrop());
        bindBtn('btn-hold', () => this.hold());

        // 顶部工具栏
        document.getElementById('pause-btn').addEventListener('click', () => this.togglePause());
        document.getElementById('restart-btn').addEventListener('click', () => this.resetGame());
        
        const soundBtn = document.getElementById('sound-btn');
        soundBtn.addEventListener('click', () => {
          sound.enabled = !sound.enabled;
          soundBtn.innerText = sound.enabled ? '🔊' : '🔇';
        });

        // 遮罩按钮
        document.getElementById('overlay-action-btn').addEventListener('click', () => {
          if (this.isPaused) {
            this.togglePause();
          } else {
            this.resetGame();
          }
        });
      }

      start() {
        this.lastTime = performance.now();
        this.update();
      }
    }

    // 启动游戏实例
    window.addEventListener('DOMContentLoaded', () => {
      const game = new TetrisGame();
      game.start();
    });
  </script>
</body>
</html>
"""

def main():
    desktop_dir = os.path.expanduser('~/Desktop')
    out_file = os.path.join(desktop_dir, '俄罗斯方块.html')
    
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(HTML_CONTENT)
    
    file_size_kb = os.path.getsize(out_file) / 1024
    print("Successfully generated Tetris game to desktop!")
    print(f"Path: {out_file}")
    print(f"Size: {file_size_kb:.2f} KB")

if __name__ == '__main__':
    main()
