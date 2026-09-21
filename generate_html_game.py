import os

script_content = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>经典坦克大战 1990 - 豪华典藏版</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            user-select: none;
        }
        body {
            background-color: #1e1e24;
            color: #fff;
            font-family: 'Courier New', Consolas, 'Microsoft YaHei', monospace;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 10px;
        }
        .header {
            margin-bottom: 8px;
            text-align: center;
        }
        .header h1 {
            font-size: 26px;
            color: #ffbe0b;
            text-shadow: 2px 2px 0 #fb5607, 4px 4px 0 #000;
            letter-spacing: 3px;
        }
        .header p {
            font-size: 12px;
            color: #aaa;
            margin-top: 2px;
        }
        .main-container {
            display: flex;
            background: #000;
            border: 8px solid #4a4e69;
            border-radius: 8px;
            box-shadow: 0 12px 30px rgba(0,0,0,0.8), 0 0 15px rgba(255,190,11,0.25);
            position: relative;
        }
        #gameCanvas {
            background-color: #000;
            display: block;
            image-rendering: pixelated;
        }
        .sidebar {
            width: 170px;
            background: #8d99ae;
            border-left: 5px solid #2b2d42;
            padding: 12px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: space-between;
            color: #111;
            font-weight: bold;
        }
        .radar-box {
            width: 100%;
            background: #2b2d42;
            border-radius: 6px;
            padding: 8px 6px;
            color: #edf2f4;
            text-align: center;
        }
        .radar-title {
            font-size: 13px;
            margin-bottom: 6px;
            color: #ffbe0b;
        }
        .enemy-radar {
            display: grid;
            grid-template-columns: repeat(2, 22px);
            justify-content: center;
            gap: 5px 8px;
            min-height: 180px;
        }
        .tank-mini-icon {
            width: 20px;
            height: 20px;
            background: #111;
            border-radius: 3px;
            position: relative;
        }
        .tank-mini-icon::before {
            content: "";
            position: absolute;
            top: 2px; left: 8px; width: 4px; height: 16px;
            background: #e63946;
            border-radius: 2px;
        }
        .tank-mini-icon::after {
            content: "";
            position: absolute;
            top: 6px; left: 4px; width: 12px; height: 8px;
            background: #f1faee;
            border-radius: 2px;
        }
        .player-card {
            width: 100%;
            background: #edf2f4;
            border: 2px solid #2b2d42;
            border-radius: 6px;
            padding: 8px;
            font-size: 13px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.15);
        }
        .player-card.p1 {
            border-left: 6px solid #e63946;
        }
        .player-card.p2 {
            border-left: 6px solid #2a9d8f;
            display: none;
        }
        .card-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 3px 0;
        }
        .flag-box {
            width: 100%;
            text-align: center;
            background: #e76f51;
            border: 2px solid #264653;
            color: #fff;
            padding: 8px 4px;
            border-radius: 6px;
            text-shadow: 1px 1px 0 #000;
        }
        .flag-box .title {
            font-size: 12px;
            letter-spacing: 2px;
        }
        .flag-box .stage-num {
            font-size: 22px;
            font-weight: 900;
        }
        .controls-info {
            margin-top: 10px;
            background: #2b2d42;
            border: 1px solid #4a4e69;
            border-radius: 6px;
            padding: 8px 16px;
            max-width: 690px;
            width: 100%;
            font-size: 13px;
            display: flex;
            justify-content: space-around;
            color: #edf2f4;
        }
        .controls-info span.key {
            color: #ffbe0b;
            font-weight: bold;
            background: #1e1e24;
            padding: 2px 6px;
            border-radius: 4px;
            border: 1px solid #555;
            margin: 0 2px;
        }
        .button-bar {
            margin-top: 10px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            justify-content: center;
        }
        button {
            background: #264653;
            color: #fff;
            border: 2px solid #2a9d8f;
            padding: 6px 14px;
            font-size: 13px;
            font-weight: bold;
            border-radius: 5px;
            cursor: pointer;
            transition: all 0.2s;
        }
        button:hover {
            background: #2a9d8f;
            color: #000;
        }
        button:active {
            transform: scale(0.96);
        }
        #hudOverlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 520px;
            height: 520px;
            pointer-events: none;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }
        .hud-text {
            color: #e63946;
            font-size: 38px;
            font-weight: 900;
            text-shadow: 3px 3px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000;
            letter-spacing: 4px;
            display: none;
            animation: pulse 1s infinite alternate;
        }
        @keyframes pulse {
            0% { transform: scale(1); }
            100% { transform: scale(1.08); }
        }
    </style>
</head>
<body>

    <div class="header">
        <h1>&#128163; 坦克大战 BATTLE CITY 1990</h1>
        <p>经典街机 FC 复刻 · 双人作战 · 炫彩升级道具 · 原生音效</p>
    </div>

    <div class="main-container">
        <div style="position: relative;">
            <canvas id="gameCanvas" width="520" height="520"></canvas>
            <div id="hudOverlay">
                <div id="gameOverBanner" class="hud-text">GAME OVER</div>
                <div id="stageClearBanner" class="hud-text" style="color: #2a9d8f;">STAGE CLEAR!</div>
                <div id="pauseBanner" class="hud-text" style="color: #ffbe0b;">PAUSED</div>
            </div>
        </div>

        <div class="sidebar">
            <div class="radar-box">
                <div class="radar-title">敌军剩余: <span id="radarCount">20</span></div>
                <div class="enemy-radar" id="radarList"></div>
            </div>

            <div class="player-card p1" id="p1Card">
                <div class="card-row"><span style="color:#e63946; font-weight:900;">1P 玩家</span><span id="p1Star">★ 等级 1</span></div>
                <div class="card-row"><span>&#10084; 生命:</span><span id="p1Lives" style="color:#e63946; font-size:16px;">3</span></div>
                <div class="card-row"><span>&#127942; 分数:</span><span id="p1Score">0</span></div>
            </div>

            <div class="player-card p2" id="p2Card">
                <div class="card-row"><span style="color:#2a9d8f; font-weight:900;">2P 玩家</span><span id="p2Star">★ 等级 1</span></div>
                <div class="card-row"><span>&#10084; 生命:</span><span id="p2Lives" style="color:#2a9d8f; font-size:16px;">3</span></div>
                <div class="card-row"><span>&#127942; 分数:</span><span id="p2Score">0</span></div>
            </div>

            <div class="flag-box">
                <div class="title">&#127988; MISSION</div>
                <div class="stage-num" id="stageText">关卡 1</div>
            </div>
        </div>
    </div>

    <div class="controls-info">
        <div><strong style="color:#ffbe0b;">1P:</strong> <span class="key">W</span><span class="key">A</span><span class="key">S</span><span class="key">D</span> 移动 | <span class="key">J</span> 或 <span class="key">空格</span> 开火</div>
        <div id="p2Help" style="display:none;"><strong style="color:#2a9d8f;">2P:</strong> <span class="key">↑</span><span class="key">↓</span><span class="key">←</span><span class="key">→</span> 移动 | <span class="key">Enter</span> 或 <span class="key">小键盘0</span> 开火</div>
        <div><span class="key">P</span> 暂停 | <span class="key">R</span> 重新开始</div>
    </div>

    <div class="button-bar">
        <button id="togglePlayerBtn" onclick="togglePlayerMode()">切换为双人模式 (2P)</button>
        <button id="soundBtn" onclick="toggleSound()">音效: 开启</button>
        <button onclick="restartCurrentGame()">重新开始</button>
        <button onclick="togglePauseGame()">暂停 / 继续</button>
        <button onclick="skipToNextStage()">跳到下一关</button>
    </div>

    <script>
        /* ================= 1. 音频合成引擎 (Web Audio API) ================= */
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
            playShoot() {
                if (!this.enabled) return;
                this.init();
                if (!this.ctx) return;
                const osc = this.ctx.createOscillator();
                const gain = this.ctx.createGain();
                osc.type = 'square';
                const now = this.ctx.currentTime;
                osc.frequency.setValueAtTime(480, now);
                osc.frequency.exponentialRampToValueAtTime(80, now + 0.12);
                gain.gain.setValueAtTime(0.18, now);
                gain.gain.exponentialRampToValueAtTime(0.01, now + 0.12);
                osc.connect(gain);
                gain.connect(this.ctx.destination);
                osc.start(now);
                osc.stop(now + 0.12);
            }
            playExplosion(isBig = false) {
                if (!this.enabled) return;
                this.init();
                if (!this.ctx) return;
                const duration = isBig ? 0.45 : 0.22;
                const bufferSize = Math.floor(this.ctx.sampleRate * duration);
                const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
                const data = buffer.getChannelData(0);
                for (let i = 0; i < bufferSize; i++) {
                    data[i] = Math.random() * 2 - 1;
                }
                const noise = this.ctx.createBufferSource();
                noise.buffer = buffer;

                const filter = this.ctx.createBiquadFilter();
                filter.type = 'lowpass';
                const now = this.ctx.currentTime;
                filter.frequency.setValueAtTime(isBig ? 600 : 900, now);
                filter.frequency.exponentialRampToValueAtTime(30, now + duration);

                const gain = this.ctx.createGain();
                gain.gain.setValueAtTime(isBig ? 0.35 : 0.2, now);
                gain.gain.exponentialRampToValueAtTime(0.01, now + duration);

                noise.connect(filter);
                filter.connect(gain);
                gain.connect(this.ctx.destination);
                noise.start(now);
            }
            playSteelHit() {
                if (!this.enabled) return;
                this.init();
                if (!this.ctx) return;
                const osc = this.ctx.createOscillator();
                const gain = this.ctx.createGain();
                osc.type = 'sine';
                const now = this.ctx.currentTime;
                osc.frequency.setValueAtTime(1100, now);
                osc.frequency.exponentialRampToValueAtTime(400, now + 0.07);
                gain.gain.setValueAtTime(0.2, now);
                gain.gain.exponentialRampToValueAtTime(0.01, now + 0.07);
                osc.connect(gain);
                gain.connect(this.ctx.destination);
                osc.start(now);
                osc.stop(now + 0.07);
            }
            playPowerUp() {
                if (!this.enabled) return;
                this.init();
                if (!this.ctx) return;
                const now = this.ctx.currentTime;
                const notes = [330, 392, 523, 659, 784];
                notes.forEach((freq, idx) => {
                    const osc = this.ctx.createOscillator();
                    const gain = this.ctx.createGain();
                    osc.type = 'triangle';
                    osc.frequency.setValueAtTime(freq, now + idx * 0.06);
                    gain.gain.setValueAtTime(0.2, now + idx * 0.06);
                    gain.gain.exponentialRampToValueAtTime(0.01, now + idx * 0.06 + 0.09);
                    osc.connect(gain);
                    gain.connect(this.ctx.destination);
                    osc.start(now + idx * 0.06);
                    osc.stop(now + idx * 0.06 + 0.09);
                });
            }
            playStageStart() {
                if (!this.enabled) return;
                this.init();
                if (!this.ctx) return;
                const notes = [262, 330, 392, 523, 392, 523];
                const now = this.ctx.currentTime;
                notes.forEach((f, i) => {
                    const osc = this.ctx.createOscillator();
                    const gain = this.ctx.createGain();
                    osc.type = 'square';
                    osc.frequency.setValueAtTime(f, now + i * 0.1);
                    gain.gain.setValueAtTime(0.15, now + i * 0.1);
                    gain.gain.exponentialRampToValueAtTime(0.01, now + i * 0.1 + 0.12);
                    osc.connect(gain);
                    gain.connect(this.ctx.destination);
                    osc.start(now + i * 0.1);
                    osc.stop(now + i * 0.1 + 0.12);
                });
            }
            playGameOver() {
                if (!this.enabled) return;
                this.init();
                if (!this.ctx) return;
                const now = this.ctx.currentTime;
                const freqs = [350, 320, 280, 220, 160];
                freqs.forEach((f, i) => {
                    const osc = this.ctx.createOscillator();
                    const gain = this.ctx.createGain();
                    osc.type = 'sawtooth';
                    osc.frequency.setValueAtTime(f, now + i * 0.18);
                    gain.gain.setValueAtTime(0.25, now + i * 0.18);
                    gain.gain.exponentialRampToValueAtTime(0.01, now + i * 0.18 + 0.22);
                    osc.connect(gain);
                    gain.connect(this.ctx.destination);
                    osc.start(now + i * 0.18);
                    osc.stop(now + i * 0.18 + 0.22);
                });
            }
        }
        const sound = new SoundEngine();

        /* ================= 2. 经典常量与地形定义 ================= */
        const CELL_SIZE = 20; // 26x26 格，每格 20 像素，总尺寸 520x520
        const GRID_ROWS = 26;
        const GRID_COLS = 26;
        const CANVAS_SIZE = 520;

        // 地形类型代码
        const T_EMPTY = 0;
        const T_BRICK = 1;   // 红砖，普通炮弹可碎
        const T_STEEL = 2;   // 铁墙，普通反弹，高级炮弹可碎
        const T_GRASS = 3;   // 丛林，坦克隐蔽穿行
        const T_WATER = 4;   // 水池，坦克不可过，炮弹穿行
        const T_BASE  = 9;   // 基地老鹰

        const DIR_UP    = 0;
        const DIR_DOWN  = 1;
        const DIR_LEFT  = 2;
        const DIR_RIGHT = 3;

        // 预设关卡地图 (5关设计)
        const MAP_PRESETS = [
            // 关卡 1: 经典第一关
            [
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
            ],
            // 关卡 2: 河流与岛屿
            [
                "00000000000000000000000000",
                "00110000110000001100001100",
                "00110000110000001100001100",
                "00444444444400444444444400",
                "00444444444400444444444400",
                "00110011001122110011001100",
                "00110011001122110011001100",
                "00000011000000000011000000",
                "22220011001111110011002222",
                "00000000001100110000000000",
                "00111100001100110000111100",
                "00111100444444444400111100",
                "00000000444444444400000000",
                "00111100000000000000111100",
                "00111100110000001100111100",
                "00000000110022001100000000",
                "00220000110022001100002200",
                "00220011111111111111002200",
                "00000011111111111111000000",
                "00110000000000000000001100",
                "00110011000000000011001100",
                "00000011000000000011000000",
                "00000000000000000000000000",
                "00000000000111100000000000",
                "00000000000199100000000000",
                "00000000000199100000000000"
            ],
            // 关卡 3: 丛林迷踪
            [
                "00000000000000000000000000",
                "00333300110000110033330000",
                "00333300110000110033330000",
                "00333300112222110033330000",
                "00000000002222000000000000",
                "11110033333333333300111100",
                "11110033333333333300111100",
                "00000033001111003300000000",
                "00220033001111003300220000",
                "00220000001111000000220000",
                "00000011000000001100000000",
                "00111111003333001111110000",
                "00111111003333001111110000",
                "00000000003333000000000000",
                "00333300111111110033330000",
                "00333300111111110033330000",
                "00000000000000000000000000",
                "22220011000000001100222200",
                "22220011001111001100222200",
                "00000000001111000000000000",
                "00110000000000000000001100",
                "00110000000000000000001100",
                "00000000000000000000000000",
                "00000000000111100000000000",
                "00000000000199100000000000",
                "00000000000199100000000000"
            ],
            // 关卡 4: 钢铁要塞
            [
                "00000000000000000000000000",
                "00220011002222001100220000",
                "00220011002222001100220000",
                "00220011000000001100220000",
                "00000000002222000000000000",
                "00111122002222002211110000",
                "00111122000000002211110000",
                "00000000001111000000000000",
                "22220011001111001100222200",
                "22220011000000001100222200",
                "00000011002222001100000000",
                "00110000002222000000110000",
                "00110022000000002200110000",
                "00000022001111002200000000",
                "00220000001111000000220000",
                "00220011110000111100220000",
                "00000011110000111100000000",
                "00110000002222000000110000",
                "00110022002222002200110000",
                "00000022000000002200000000",
                "00000000001111000000000000",
                "00220000001111000000220000",
                "00220000000000000000220000",
                "00000000000111100000000000",
                "00000000000199100000000000",
                "00000000000199100000000000"
            ],
            // 关卡 5: 决战时刻
            [
                "00000000000000000000000000",
                "00112211004444001122110000",
                "00112211004444001122110000",
                "00110011000000001100110000",
                "00333333002222003333330000",
                "00333333002222003333330000",
                "00000000001111000000000000",
                "22110044440000444400112200",
                "22110044440000444400112200",
                "00000000003333000000000000",
                "00112211003333001122110000",
                "00112211000000001122110000",
                "00000000002222000000000000",
                "00444400112222110044440000",
                "00444400110000110044440000",
                "00000000000000000000000000",
                "00333300111111110033330000",
                "00333300111111110033330000",
                "00000000220000220000000000",
                "00220000220000220000220000",
                "00220011000000001100220000",
                "00000011000000001100000000",
                "00000000000000000000000000",
                "00000000000111100000000000",
                "00000000000199100000000000",
                "00000000000199100000000000"
            ]
        ];

        /* ================= 3. 游戏全局状态 ================= */
        const canvas = document.getElementById('gameCanvas');
        const ctx = canvas.getContext('2d');

        let isTwoPlayer = false;
        let currentStageIdx = 0;
        let isPaused = false;
        let isGameOver = false;
        let isVictory = false;

        let map = [];
        let p1 = null;
        let p2 = null;
        let enemies = [];
        let bullets = [];
        let explosions = [];
        let powerUps = [];

        // 基地状态
        let baseAlive = true;
        let shovelTimer = 0; // 铁锹保护倒计时

        // 关卡敌人生成控制
        let remainingEnemiesCount = 20; // 本关待刷新敌人数
        let enemySpawnTimer = 0;
        let freezeTimer = 0; // 怀表冻结时间

        // 键盘按键捕获状态
        const keys = {};
        window.addEventListener('keydown', (e) => {
            keys[e.code] = true;
            sound.init();
            if (e.code === 'KeyP') togglePauseGame();
            if (e.code === 'KeyR') restartCurrentGame();
            // 阻止网页在按方向键/空格时滚动
            if (['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Space'].includes(e.code)) {
                e.preventDefault();
            }
        });
        window.addEventListener('keyup', (e) => {
            keys[e.code] = false;
        });

        /* ================= 4. 精细绘图工具函数 ================= */
        function drawBrick(x, y, w, h) {
            ctx.fillStyle = '#b33918';
            ctx.fillRect(x, y, w, h);
            // 砖缝细节
            ctx.strokeStyle = '#2b1d0c';
            ctx.lineWidth = 1;
            ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
            // 砖块高光
            ctx.fillStyle = '#d35400';
            ctx.fillRect(x + 2, y + 2, w - 4, 2);
        }

        function drawSteel(x, y, w, h) {
            ctx.fillStyle = '#bdc3c7';
            ctx.fillRect(x, y, w, h);
            ctx.fillStyle = '#ecf0f1';
            ctx.fillRect(x + 2, y + 2, w - 4, h - 4);
            ctx.fillStyle = '#7f8c8d';
            ctx.fillRect(x + 4, y + 4, w - 8, h - 8);
            // 铆钉
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(x + 3, y + 3, 2, 2);
        }

        function drawWater(x, y, w, h, animTick) {
            ctx.fillStyle = '#2980b9';
            ctx.fillRect(x, y, w, h);
            // 动态波纹
            ctx.fillStyle = '#3498db';
            const offset = Math.floor((animTick / 10) % 4) * 2;
            ctx.fillRect(x, y + offset, w, 3);
        }

        function drawGrass(x, y, w, h) {
            ctx.fillStyle = '#27ae60';
            ctx.fillRect(x, y, w, h);
            ctx.fillStyle = '#2ecc71';
            // 树叶点缀
            ctx.fillRect(x + 2, y + 3, 4, 4);
            ctx.fillRect(x + 10, y + 8, 5, 5);
            ctx.fillStyle = '#1e8449';
            ctx.fillRect(x + 8, y + 2, 4, 4);
        }

        function drawBase(x, y, alive) {
            if (alive) {
                // 绘制金色雄鹰
                ctx.fillStyle = '#f39c12';
                ctx.fillRect(x + 4, y + 4, 32, 32);
                ctx.fillStyle = '#f1c40f';
                ctx.fillRect(x + 8, y + 8, 24, 24);
                // 鹰头与鹰眼
                ctx.fillStyle = '#e67e22';
                ctx.beginPath();
                ctx.arc(x + 20, y + 16, 7, 0, Math.PI * 2);
                ctx.fill();
                ctx.fillStyle = '#000';
                ctx.fillRect(x + 18, y + 14, 3, 3);
                ctx.fillStyle = '#c0392b';
                ctx.fillRect(x + 16, y + 24, 8, 8); // 勋章
            } else {
                // 废墟
                ctx.fillStyle = '#555';
                ctx.fillRect(x + 4, y + 4, 32, 32);
                ctx.fillStyle = '#333';
                ctx.fillRect(x + 8, y + 8, 24, 24);
                // 废弃骷髅旗
                ctx.fillStyle = '#e74c3c';
                ctx.fillRect(x + 10, y + 12, 20, 4);
                ctx.fillRect(x + 18, y + 6, 4, 26);
            }
        }

        /* ================= 5. 地图载入与维护 ================= */
        function loadStageMap(stageIdx) {
            const raw = MAP_PRESETS[stageIdx % MAP_PRESETS.length];
            map = [];
            for (let r = 0; r < GRID_ROWS; r++) {
                const rowStr = raw[r] || "0".repeat(GRID_COLS);
                const row = [];
                for (let c = 0; c < GRID_COLS; c++) {
                    row.push(parseInt(rowStr[c]) || 0);
                }
                map.push(row);
            }
        }

        // 铁锹道具：老鹰周围设为铁墙或恢复砖墙
        function setBaseFortress(type) {
            const positions = [
                [23, 11], [23, 12], [23, 13], [23, 14],
                [24, 11], [24, 14],
                [25, 11], [25, 14]
            ];
            for (const [r, c] of positions) {
                if (map[r] && map[r][c] !== undefined) {
                    map[r][c] = type;
                }
            }
        }

        /* ================= 6. 实体类定义 ================= */
        // 炮弹类
        class Bullet {
            constructor(x, y, dir, speed, isPlayer, owner, canBreakSteel = false) {
                this.x = x;
                this.y = y;
                this.dir = dir;
                this.speed = speed;
                this.isPlayer = isPlayer;
                this.owner = owner;
                this.canBreakSteel = canBreakSteel;
                this.size = 5;
                this.active = true;
            }
            update() {
                if (!this.active) return;
                switch (this.dir) {
                    case DIR_UP:    this.y -= this.speed; break;
                    case DIR_DOWN:  this.y += this.speed; break;
                    case DIR_LEFT:  this.x -= this.speed; break;
                    case DIR_RIGHT: this.x += this.speed; break;
                }
                // 边界检测
                if (this.x < 0 || this.x > CANVAS_SIZE || this.y < 0 || this.y > CANVAS_SIZE) {
                    this.active = false;
                    explosions.push(new Explosion(this.x, this.y, false));
                    return;
                }
                // 地形碰撞
                this.checkMapCollision();
            }
            checkMapCollision() {
                const col = Math.floor(this.x / CELL_SIZE);
                const row = Math.floor(this.y / CELL_SIZE);
                if (row >= 0 && row < GRID_ROWS && col >= 0 && col < GRID_COLS) {
                    const tile = map[row][col];
                    if (tile === T_BRICK) {
                        map[row][col] = T_EMPTY;
                        this.active = false;
                        sound.playExplosion(false);
                        explosions.push(new Explosion(this.x, this.y, false));
                    } else if (tile === T_STEEL) {
                        if (this.canBreakSteel) {
                            map[row][col] = T_EMPTY;
                            sound.playExplosion(false);
                        } else {
                            sound.playSteelHit();
                        }
                        this.active = false;
                        explosions.push(new Explosion(this.x, this.y, false));
                    } else if (tile === T_BASE) {
                        if (baseAlive) {
                            baseAlive = false;
                            this.active = false;
                            sound.playGameOver();
                            explosions.push(new Explosion(24 * CELL_SIZE + 20, 24 * CELL_SIZE + 20, true));
                            triggerGameOver();
                        }
                    }
                }
            }
            draw() {
                ctx.fillStyle = this.isPlayer ? '#ffea00' : '#ffffff';
                ctx.beginPath();
                ctx.arc(this.x, this.y, 3, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        // 爆炸动画类
        class Explosion {
            constructor(x, y, isBig = false) {
                this.x = x;
                this.y = y;
                this.isBig = isBig;
                this.frame = 0;
                this.maxFrames = isBig ? 24 : 14;
            }
            update() {
                this.frame++;
            }
            draw() {
                const progress = this.frame / this.maxFrames;
                const radius = (this.isBig ? 32 : 16) * (1 + progress * 0.5);
                ctx.save();
                ctx.beginPath();
                ctx.arc(this.x, this.y, radius * (1 - progress * 0.3), 0, Math.PI * 2);
                ctx.fillStyle = progress < 0.3 ? '#ffffff' : (progress < 0.6 ? '#f39c12' : '#c0392b');
                ctx.fill();
                ctx.beginPath();
                ctx.arc(this.x, this.y, radius * 0.5 * (1 - progress), 0, Math.PI * 2);
                ctx.fillStyle = '#ffffff';
                ctx.fill();
                ctx.restore();
            }
            isFinished() {
                return this.frame >= this.maxFrames;
            }
        }

        // 道具类
        const POWER_STAR    = 1; // 升星
        const POWER_BOMB    = 2; // 全屏秒杀
        const POWER_CLOCK   = 3; // 冻结敌人
        const POWER_SHOVEL  = 4; // 铁堡垒
        const POWER_HELMET  = 5; // 无敌护盾
        const POWER_TANK    = 6; // +1 生命

        class PowerUp {
            constructor(x, y, type) {
                this.x = x;
                this.y = y;
                this.type = type;
                this.width = 24;
                this.height = 24;
                this.timer = 600; // 存活帧数 (约10秒)
                this.flashTick = 0;
            }
            update() {
                this.timer--;
                this.flashTick++;
            }
            draw() {
                if (this.timer < 120 && Math.floor(this.flashTick / 10) % 2 === 0) {
                    return; // 闪烁消失前奏
                }
                ctx.save();
                ctx.fillStyle = '#111';
                ctx.fillRect(this.x, this.y, this.width, this.height);
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 1.5;
                ctx.strokeRect(this.x, this.y, this.width, this.height);

                ctx.font = '14px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                const cx = this.x + 12;
                const cy = this.y + 12;

                switch(this.type) {
                    case POWER_STAR:
                        ctx.fillStyle = '#f1c40f';
                        ctx.fillText('★', cx, cy);
                        break;
                    case POWER_BOMB:
                        ctx.fillStyle = '#e74c3c';
                        ctx.fillText('💣', cx, cy);
                        break;
                    case POWER_CLOCK:
                        ctx.fillStyle = '#3498db';
                        ctx.fillText('⏱', cx, cy);
                        break;
                    case POWER_SHOVEL:
                        ctx.fillStyle = '#9b59b6';
                        ctx.fillText('⛏', cx, cy);
                        break;
                    case POWER_HELMET:
                        ctx.fillStyle = '#e67e22';
                        ctx.fillText('🛡', cx, cy);
                        break;
                    case POWER_TANK:
                        ctx.fillStyle = '#2ecc71';
                        ctx.fillText('❤', cx, cy);
                        break;
                }
                ctx.restore();
            }
        }

        // 坦克基类
        class Tank {
            constructor(x, y, dir, speed, color) {
                this.x = x;
                this.y = y;
                this.size = 28; // 像素
                this.dir = dir;
                this.speed = speed;
                this.color = color;
                this.bulletCooldown = 0;
                this.shieldTimer = 0;
                this.treadAnim = 0;
            }
            canMoveTo(nx, ny) {
                // 屏幕边界
                if (nx < 0 || nx + this.size > CANVAS_SIZE || ny < 0 || ny + this.size > CANVAS_SIZE) {
                    return false;
                }
                // 检查所占单元格地形
                const left = Math.floor(nx / CELL_SIZE);
                const right = Math.floor((nx + this.size - 1) / CELL_SIZE);
                const top = Math.floor(ny / CELL_SIZE);
                const bottom = Math.floor((ny + this.size - 1) / CELL_SIZE);

                for (let r = top; r <= bottom; r++) {
                    for (let c = left; c <= right; c++) {
                        if (r >= 0 && r < GRID_ROWS && c >= 0 && c < GRID_COLS) {
                            const tile = map[r][c];
                            if (tile === T_BRICK || tile === T_STEEL || tile === T_WATER || tile === T_BASE) {
                                return false;
                            }
                        }
                    }
                }
                return true;
            }
            drawTankBody(primaryColor, secondaryColor) {
                const cx = this.x + this.size / 2;
                const cy = this.y + this.size / 2;
                ctx.save();
                ctx.translate(cx, cy);

                let angle = 0;
                if (this.dir === DIR_DOWN) angle = Math.PI;
                if (this.dir === DIR_LEFT) angle = -Math.PI / 2;
                if (this.dir === DIR_RIGHT) angle = Math.PI / 2;
                ctx.rotate(angle);

                // 履带
                const trackOffset = (this.treadAnim % 2 === 0) ? 0 : 2;
                ctx.fillStyle = '#111';
                ctx.fillRect(-14, -14, 6, 28); // 左履带
                ctx.fillRect(8, -14, 6, 28);  // 右履带
                ctx.fillStyle = '#777';
                for (let i = -12; i < 14; i += 6) {
                    ctx.fillRect(-14, i + trackOffset, 6, 2);
                    ctx.fillRect(8, i + trackOffset, 6, 2);
                }

                // 主车身
                ctx.fillStyle = primaryColor;
                ctx.fillRect(-8, -10, 16, 20);

                // 炮塔
                ctx.fillStyle = secondaryColor;
                ctx.fillRect(-5, -5, 10, 10);

                // 炮管
                ctx.fillStyle = '#fff';
                ctx.fillRect(-2, -14, 4, 10);

                ctx.restore();

                // 护盾力场光环
                if (this.shieldTimer > 0) {
                    ctx.save();
                    ctx.strokeStyle = `hsl(${(Date.now() / 4) % 360}, 100%, 65%)`;
                    ctx.lineWidth = 2.5;
                    ctx.beginPath();
                    ctx.arc(cx, cy, 18, 0, Math.PI * 2);
                    ctx.stroke();
                    ctx.restore();
                }
            }
        }

        // 玩家坦克
        class PlayerTank extends Tank {
            constructor(x, y, id, color) {
                super(x, y, DIR_UP, 2.2, color);
                this.id = id;
                this.level = 0; // 0:普通, 1:快速炮, 2:双发连射, 3:可碎铁
                this.lives = 3;
                this.score = 0;
                this.shieldTimer = 180; // 出生 3 秒无敌
                this.spawnX = x;
                this.spawnY = y;
            }
            respawn() {
                this.x = this.spawnX;
                this.y = this.spawnY;
                this.dir = DIR_UP;
                this.shieldTimer = 180;
                this.level = Math.max(0, this.level - 1); // 扣一级
            }
            upgrade() {
                if (this.level < 3) this.level++;
                updateHUD();
            }
            update() {
                if (this.shieldTimer > 0) this.shieldTimer--;
                if (this.bulletCooldown > 0) this.bulletCooldown--;

                let moving = false;
                let nx = this.x;
                let ny = this.y;

                if (this.id === 1) {
                    // 1P: WASD + Space/J
                    if (keys['KeyW']) { this.dir = DIR_UP; ny -= this.speed; moving = true; }
                    else if (keys['KeyS']) { this.dir = DIR_DOWN; ny += this.speed; moving = true; }
                    else if (keys['KeyA']) { this.dir = DIR_LEFT; nx -= this.speed; moving = true; }
                    else if (keys['KeyD']) { this.dir = DIR_RIGHT; nx += this.speed; moving = true; }
                    if ((keys['KeyJ'] || keys['Space']) && this.bulletCooldown <= 0) {
                        this.shoot();
                    }
                } else if (this.id === 2 && isTwoPlayer) {
                    // 2P: 方向键 + Enter/Numpad0
                    if (keys['ArrowUp']) { this.dir = DIR_UP; ny -= this.speed; moving = true; }
                    else if (keys['ArrowDown']) { this.dir = DIR_DOWN; ny += this.speed; moving = true; }
                    else if (keys['ArrowLeft']) { this.dir = DIR_LEFT; nx -= this.speed; moving = true; }
                    else if (keys['ArrowRight']) { this.dir = DIR_RIGHT; nx += this.speed; moving = true; }
                    if ((keys['Enter'] || keys['Numpad0']) && this.bulletCooldown <= 0) {
                        this.shoot();
                    }
                }

                if (moving) {
                    this.treadAnim++;
                    // 碰撞检查
                    if (this.canMoveTo(nx, ny)) {
                        this.x = nx;
                        this.y = ny;
                    } else {
                        // 顺滑转弯辅助 (Corner Assist)
                        if (this.dir === DIR_UP || this.dir === DIR_DOWN) {
                            const align = Math.round(this.x / CELL_SIZE) * CELL_SIZE;
                            if (Math.abs(this.x - align) <= 6 && this.canMoveTo(align, ny)) {
                                this.x = align;
                                this.y = ny;
                            }
                        } else {
                            const align = Math.round(this.y / CELL_SIZE) * CELL_SIZE;
                            if (Math.abs(this.y - align) <= 6 && this.canMoveTo(nx, align)) {
                                this.x = nx;
                                this.y = align;
                            }
                        }
                    }
                }

                // 道具收集检测
                for (let i = powerUps.length - 1; i >= 0; i--) {
                    const p = powerUps[i];
                    if (this.x < p.x + p.width && this.x + this.size > p.x &&
                        this.y < p.y + p.height && this.y + this.size > p.y) {
                        applyPowerUp(p.type, this);
                        powerUps.splice(i, 1);
                        sound.playPowerUp();
                    }
                }
            }
            shoot() {
                const bSpeed = this.level >= 1 ? 6.5 : 4.5;
                const canBreakSteel = this.level >= 3;
                const cx = this.x + this.size / 2;
                const cy = this.y + this.size / 2;

                // 统计当前属于自己的活跃子弹数
                const myBullets = bullets.filter(b => b.owner === this && b.active);
                const maxBullets = this.level >= 2 ? 2 : 1;
                if (myBullets.length >= maxBullets) return;

                let bx = cx;
                let by = cy;
                if (this.dir === DIR_UP) by = this.y - 2;
                if (this.dir === DIR_DOWN) by = this.y + this.size + 2;
                if (this.dir === DIR_LEFT) bx = this.x - 2;
                if (this.dir === DIR_RIGHT) bx = this.x + this.size + 2;

                bullets.push(new Bullet(bx, by, this.dir, bSpeed, true, this, canBreakSteel));
                this.bulletCooldown = 15;
                sound.playShoot();
            }
            draw() {
                const pColor = this.id === 1 ? '#e5a93b' : '#27ae60';
                const sColor = this.level >= 2 ? '#2980b9' : '#c0392b';
                this.drawTankBody(pColor, sColor);
            }
        }

        // 敌方坦克种类
        const ENEMY_BASIC = 1;  // 普通灰坦
        const ENEMY_FAST  = 2;  // 极速黄色侦察
        const ENEMY_POWER = 3;  // 强攻速射坦克
        const ENEMY_ARMOR = 4;  // 重装血牛绿坦

        class EnemyTank extends Tank {
            constructor(x, y, type, hasItem = false) {
                let spd = 1.3;
                let hp = 1;
                let col = '#95a5a6';

                if (type === ENEMY_FAST) {
                    spd = 2.4;
                    col = '#f39c12';
                } else if (type === ENEMY_POWER) {
                    spd = 1.6;
                    col = '#3498db';
                } else if (type === ENEMY_ARMOR) {
                    spd = 1.1;
                    hp = 4;
                    col = '#27ae60';
                }

                super(x, y, DIR_DOWN, spd, col);
                this.type = type;
                this.hp = hp;
                this.maxHp = hp;
                this.hasItem = hasItem; // 击毁必定掉道具
                this.changeDirTimer = Math.floor(Math.random() * 60) + 30;
                this.shootTimer = Math.floor(Math.random() * 80) + 40;
                this.colorTick = 0;
            }
            update() {
                if (freezeTimer > 0) return; // 被时钟定身

                this.colorTick++;
                this.treadAnim++;
                this.changeDirTimer--;
                this.shootTimer--;

                // AI 随机转向与倾向巡航
                if (this.changeDirTimer <= 0) {
                    this.changeDirTimer = Math.floor(Math.random() * 90) + 40;
                    // 40% 几率向下朝向基地进攻
                    if (Math.random() < 0.45) {
                        this.dir = DIR_DOWN;
                    } else {
                        this.dir = Math.floor(Math.random() * 4);
                    }
                }

                // 前进
                let nx = this.x;
                let ny = this.y;
                switch (this.dir) {
                    case DIR_UP:    ny -= this.speed; break;
                    case DIR_DOWN:  ny += this.speed; break;
                    case DIR_LEFT:  nx -= this.speed; break;
                    case DIR_RIGHT: nx += this.speed; break;
                }

                if (this.canMoveTo(nx, ny)) {
                    this.x = nx;
                    this.y = ny;
                } else {
                    // 撞墙立即改向
                    this.dir = Math.floor(Math.random() * 4);
                    this.changeDirTimer = Math.floor(Math.random() * 50) + 20;
                }

                // AI 射击
                if (this.shootTimer <= 0) {
                    this.shootTimer = Math.floor(Math.random() * 90) + 50;
                    this.shoot();
                }
            }
            shoot() {
                const bSpeed = this.type === ENEMY_POWER ? 6.0 : 3.8;
                const cx = this.x + this.size / 2;
                const cy = this.y + this.size / 2;
                let bx = cx;
                let by = cy;
                if (this.dir === DIR_UP) by = this.y - 2;
                if (this.dir === DIR_DOWN) by = this.y + this.size + 2;
                if (this.dir === DIR_LEFT) bx = this.x - 2;
                if (this.dir === DIR_RIGHT) bx = this.x + this.size + 2;

                bullets.push(new Bullet(bx, by, this.dir, bSpeed, false, this));
            }
            draw() {
                let mainCol = this.color;
                // 重装坦克扣血变色
                if (this.type === ENEMY_ARMOR) {
                    if (this.hp === 3) mainCol = '#f1c40f';
                    else if (this.hp === 2) mainCol = '#e67e22';
                    else if (this.hp === 1) mainCol = '#e74c3c';
                }
                // 掉道具坦克红白闪烁
                if (this.hasItem && Math.floor(this.colorTick / 8) % 2 === 0) {
                    mainCol = '#ff0055';
                }
                this.drawTankBody(mainCol, '#2c3e50');
            }
        }

        /* ================= 7. 道具生效与生成逻辑 ================= */
        function spawnPowerUp(x, y) {
            const types = [POWER_STAR, POWER_BOMB, POWER_CLOCK, POWER_SHOVEL, POWER_HELMET, POWER_TANK];
            const chosen = types[Math.floor(Math.random() * types.length)];
            powerUps.push(new PowerUp(x, y, chosen));
        }

        function applyPowerUp(type, player) {
            switch (type) {
                case POWER_STAR:
                    player.upgrade();
                    break;
                case POWER_BOMB:
                    // 全屏清怪
                    for (const enemy of enemies) {
                        explosions.push(new Explosion(enemy.x + enemy.size/2, enemy.y + enemy.size/2, true));
                        player.score += 200;
                    }
                    enemies = [];
                    sound.playExplosion(true);
                    updateHUD();
                    break;
                case POWER_CLOCK:
                    freezeTimer = 400; // 冻结敌人 7 秒
                    break;
                case POWER_SHOVEL:
                    setBaseFortress(T_STEEL);
                    shovelTimer = 600; // 铁堡垒 10 秒
                    break;
                case POWER_HELMET:
                    player.shieldTimer = 500; // 获得无敌 8 秒
                    break;
                case POWER_TANK:
                    player.lives++;
                    updateHUD();
                    break;
            }
        }

        /* ================= 8. 敌人生成与刷新控制 ================= */
        const SPAWN_POINTS = [
            { x: 1 * CELL_SIZE, y: 1 * CELL_SIZE },
            { x: 12 * CELL_SIZE, y: 1 * CELL_SIZE },
            { x: 23 * CELL_SIZE, y: 1 * CELL_SIZE }
        ];

        function trySpawnEnemy() {
            if (remainingEnemiesCount <= 0 || enemies.length >= 4 || freezeTimer > 0) return;

            enemySpawnTimer++;
            if (enemySpawnTimer >= 100) {
                enemySpawnTimer = 0;
                const spot = SPAWN_POINTS[Math.floor(Math.random() * SPAWN_POINTS.length)];
                
                // 确保刷新点没有坦克重叠
                const isBlocked = enemies.some(e => Math.hypot(e.x - spot.x, e.y - spot.y) < 32);
                if (!isBlocked) {
                    const typeRoll = Math.random();
                    let t = ENEMY_BASIC;
                    if (typeRoll < 0.3) t = ENEMY_FAST;
                    else if (typeRoll < 0.6) t = ENEMY_POWER;
                    else if (typeRoll < 0.85) t = ENEMY_ARMOR;

                    // 15% 几率携带道具
                    const hasItem = Math.random() < 0.25;
                    enemies.push(new EnemyTank(spot.x, spot.y, t, hasItem));
                    remainingEnemiesCount--;
                    updateRadar();
                }
            }
        }

        /* ================= 9. 关卡重置与生命周期 ================= */
        function initGame(stageIdx = 0) {
            currentStageIdx = stageIdx;
            isGameOver = false;
            isVictory = false;
            baseAlive = true;
            shovelTimer = 0;
            freezeTimer = 0;
            remainingEnemiesCount = 20;

            loadStageMap(currentStageIdx);

            // 玩家 1P
            p1 = new PlayerTank(8 * CELL_SIZE, 24 * CELL_SIZE, 1, '#f1c40f');
            if (isTwoPlayer) {
                p2 = new PlayerTank(16 * CELL_SIZE, 24 * CELL_SIZE, 2, '#2ecc71');
            } else {
                p2 = null;
            }

            enemies = [];
            bullets = [];
            explosions = [];
            powerUps = [];

            document.getElementById('gameOverBanner').style.display = 'none';
            document.getElementById('stageClearBanner').style.display = 'none';
            document.getElementById('pauseBanner').style.display = 'none';

            sound.playStageStart();
            updateHUD();
            updateRadar();
        }

        function triggerGameOver() {
            isGameOver = true;
            document.getElementById('gameOverBanner').style.display = 'block';
        }

        function checkStageClear() {
            if (remainingEnemiesCount === 0 && enemies.length === 0 && baseAlive && !isGameOver) {
                isVictory = true;
                document.getElementById('stageClearBanner').style.display = 'block';
                setTimeout(() => {
                    nextStage();
                }, 2500);
            }
        }

        function nextStage() {
            initGame(currentStageIdx + 1);
        }

        function restartCurrentGame() {
            initGame(currentStageIdx);
        }

        function skipToNextStage() {
            nextStage();
        }

        function togglePauseGame() {
            isPaused = !isPaused;
            document.getElementById('pauseBanner').style.display = isPaused ? 'block' : 'none';
        }

        function togglePlayerMode() {
            isTwoPlayer = !isTwoPlayer;
            const btn = document.getElementById('togglePlayerBtn');
            const p2Card = document.getElementById('p2Card');
            const p2Help = document.getElementById('p2Help');
            if (isTwoPlayer) {
                btn.innerText = '当前: 双人模式 (点击切为单人)';
                p2Card.style.display = 'block';
                p2Help.style.display = 'block';
            } else {
                btn.innerText = '切换为双人模式 (2P)';
                p2Card.style.display = 'none';
                p2Help.style.display = 'none';
            }
            restartCurrentGame();
        }

        function toggleSound() {
            sound.enabled = !sound.enabled;
            const btn = document.getElementById('soundBtn');
            btn.innerText = sound.enabled ? '音效: 开启' : '音效: 静音';
        }

        function updateHUD() {
            document.getElementById('stageText').innerText = `第 ${currentStageIdx + 1} 关`;
            if (p1) {
                document.getElementById('p1Lives').innerText = p1.lives;
                document.getElementById('p1Score').innerText = p1.score;
                document.getElementById('p1Star').innerText = `★ 等级 ${p1.level + 1}`;
            }
            if (p2 && isTwoPlayer) {
                document.getElementById('p2Lives').innerText = p2.lives;
                document.getElementById('p2Score').innerText = p2.score;
                document.getElementById('p2Star').innerText = `★ 等级 ${p2.level + 1}`;
            }
        }

        function updateRadar() {
            const radarBox = document.getElementById('radarList');
            document.getElementById('radarCount').innerText = remainingEnemiesCount + enemies.length;
            radarBox.innerHTML = '';
            const totalRemaining = remainingEnemiesCount + enemies.length;
            for (let i = 0; i < totalRemaining; i++) {
                const icon = document.createElement('div');
                icon.className = 'tank-mini-icon';
                radarBox.appendChild(icon);
            }
        }

        /* ================= 10. 核心循环 (60 FPS) ================= */
        let animTick = 0;

        function gameLoop() {
            requestAnimationFrame(gameLoop);
            if (isPaused) return;

            animTick++;

            // 铁锹保护时间衰减
            if (shovelTimer > 0) {
                shovelTimer--;
                if (shovelTimer === 0) {
                    setBaseFortress(T_BRICK); // 恢复砖墙
                }
            }

            // 时钟冻结敌人衰减
            if (freezeTimer > 0) {
                freezeTimer--;
            }

            // 1. 更新实体
            if (!isGameOver) {
                if (p1) p1.update();
                if (p2 && isTwoPlayer) p2.update();

                trySpawnEnemy();

                for (const e of enemies) e.update();
            }

            // 更新炮弹
            for (let i = bullets.length - 1; i >= 0; i--) {
                const b = bullets[i];
                b.update();
                if (!b.active) {
                    bullets.splice(i, 1);
                    continue;
                }

                // 子弹对撞抵消
                for (let j = i - 1; j >= 0; j--) {
                    const b2 = bullets[j];
                    if (b.isPlayer !== b2.isPlayer && Math.hypot(b.x - b2.x, b.y - b2.y) < 10) {
                        b.active = false;
                        b2.active = false;
                        explosions.push(new Explosion(b.x, b.y, false));
                        sound.playSteelHit();
                        break;
                    }
                }

                // 炮弹击中敌人检测
                if (b.isPlayer && b.active) {
                    for (let k = enemies.length - 1; k >= 0; k--) {
                        const en = enemies[k];
                        if (b.x > en.x && b.x < en.x + en.size && b.y > en.y && b.y < en.y + en.size) {
                            b.active = false;
                            en.hp--;
                            if (en.hp <= 0) {
                                if (en.hasItem) {
                                    spawnPowerUp(en.x, en.y);
                                }
                                explosions.push(new Explosion(en.x + en.size/2, en.y + en.size/2, true));
                                sound.playExplosion(true);
                                enemies.splice(k, 1);
                                if (b.owner) b.owner.score += en.type * 100;
                                updateHUD();
                                updateRadar();
                                checkStageClear();
                            } else {
                                explosions.push(new Explosion(b.x, b.y, false));
                                sound.playSteelHit();
                            }
                            break;
                        }
                    }
                }

                // 敌方炮弹击中玩家检测
                if (!b.isPlayer && b.active) {
                    const players = [p1, p2].filter(p => p !== null);
                    for (const pl of players) {
                        if (b.x > pl.x && b.x < pl.x + pl.size && b.y > pl.y && b.y < pl.y + pl.size) {
                            b.active = false;
                            if (pl.shieldTimer <= 0) {
                                pl.lives--;
                                updateHUD();
                                explosions.push(new Explosion(pl.x + pl.size/2, pl.y + pl.size/2, true));
                                sound.playExplosion(true);
                                if (pl.lives > 0) {
                                    pl.respawn();
                                } else {
                                    // 玩家阵亡
                                    if ((!isTwoPlayer && p1.lives <= 0) || (isTwoPlayer && p1.lives <= 0 && p2.lives <= 0)) {
                                        triggerGameOver();
                                    }
                                }
                            } else {
                                sound.playSteelHit();
                            }
                            break;
                        }
                    }
                }
            }

            // 更新爆炸效果
            for (let i = explosions.length - 1; i >= 0; i--) {
                explosions[i].update();
                if (explosions[i].isFinished()) {
                    explosions.splice(i, 1);
                }
            }

            // 更新道具
            for (let i = powerUps.length - 1; i >= 0; i--) {
                powerUps[i].update();
                if (powerUps[i].timer <= 0) {
                    powerUps.splice(i, 1);
                }
            }

            // 2. 绘制整个画面
            ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

            // 绘制底图地形 (空地、砖、铁、水、老鹰)
            for (let r = 0; r < GRID_ROWS; r++) {
                for (let c = 0; c < GRID_COLS; c++) {
                    const t = map[r][c];
                    const px = c * CELL_SIZE;
                    const py = r * CELL_SIZE;
                    if (t === T_BRICK) {
                        drawBrick(px, py, CELL_SIZE, CELL_SIZE);
                    } else if (t === T_STEEL) {
                        drawSteel(px, py, CELL_SIZE, CELL_SIZE);
                    } else if (t === T_WATER) {
                        drawWater(px, py, CELL_SIZE, CELL_SIZE, animTick);
                    }
                }
            }

            // 绘制基地老鹰
            drawBase(12 * CELL_SIZE, 24 * CELL_SIZE, baseAlive);

            // 绘制道具
            for (const p of powerUps) p.draw();

            // 绘制坦克
            for (const e of enemies) e.draw();
            if (p1 && p1.lives > 0) p1.draw();
            if (p2 && isTwoPlayer && p2.lives > 0) p2.draw();

            // 绘制草丛 (遮挡在坦克之上，带来FC原汁原味的隐蔽感)
            for (let r = 0; r < GRID_ROWS; r++) {
                for (let c = 0; c < GRID_COLS; c++) {
                    if (map[r][c] === T_GRASS) {
                        drawGrass(c * CELL_SIZE, r * CELL_SIZE, CELL_SIZE, CELL_SIZE);
                    }
                }
            }

            // 绘制炮弹
            for (const b of bullets) b.draw();

            // 绘制爆炸
            for (const ex of explosions) ex.draw();
        }

        // 启动游戏
        initGame(0);
        requestAnimationFrame(gameLoop);
    </script>
</body>
</html>
'''

# 写入文件
target_html = r'C:\Users\Administrator\Desktop\坦克大战.html'
with open(target_html, 'w', encoding='utf-8') as f:
    f.write(script_content)

sub_html = r'C:\Users\Administrator\Desktop\坦克大战\坦克大战_经典网页版.html'
with open(sub_html, 'w', encoding='utf-8') as f:
    f.write(script_content)

print('HTML game generated successfully!')
