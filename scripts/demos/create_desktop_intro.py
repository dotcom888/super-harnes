# -*- coding: utf-8 -*-
"""
生成并导出 Super 智能体纯 HTML 网页介绍至桌面
"""
import os
import sys

HTML_CONTENT = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Super-Harnes 智能体 | 工业级自主代码工程 AI Agent</title>
  <style>
    :root {
      --bg-base: #090d16;
      --bg-surface: #0f172a;
      --bg-surface-elevated: #1e293b;
      --bg-card: rgba(15, 23, 42, 0.75);
      --bg-card-hover: rgba(30, 41, 59, 0.85);
      --border-subtle: rgba(255, 255, 255, 0.08);
      --border-focus: rgba(56, 189, 248, 0.4);
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --text-faint: #64748b;
      --primary: #38bdf8;
      --primary-gradient: linear-gradient(135deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%);
      --accent-cyan: #06b6d4;
      --accent-emerald: #10b981;
      --accent-amber: #f59e0b;
      --accent-rose: #f43f5e;
      --accent-indigo: #6366f1;
      --glass-blur: blur(16px);
      --shadow-glow: 0 0 35px rgba(56, 189, 248, 0.15);
      --font-code: "JetBrains Mono", "Cascadia Code", Consolas, Monaco, monospace;
      --radius-sm: 8px;
      --radius-md: 14px;
      --radius-lg: 20px;
    }

    [data-theme="light"] {
      --bg-base: #f8fafc;
      --bg-surface: #ffffff;
      --bg-surface-elevated: #f1f5f9;
      --bg-card: rgba(255, 255, 255, 0.85);
      --bg-card-hover: rgba(248, 250, 252, 0.95);
      --border-subtle: rgba(0, 0, 0, 0.08);
      --border-focus: rgba(2, 132, 199, 0.4);
      --text-main: #0f172a;
      --text-muted: #475569;
      --text-faint: #94a3b8;
      --primary: #0284c7;
      --shadow-glow: 0 10px 30px rgba(2, 132, 199, 0.1);
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    html {
      scroll-behavior: smooth;
    }

    body {
      background-color: var(--bg-base);
      color: var(--text-main);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      line-height: 1.6;
      overflow-x: hidden;
      transition: background-color 0.3s ease, color 0.3s ease;
    }

    /* 背景装饰粒子光晕 */
    .bg-glow-container {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      pointer-events: none;
      z-index: 0;
      overflow: hidden;
    }
    .glow-blob {
      position: absolute;
      width: 600px;
      height: 600px;
      border-radius: 50%;
      filter: blur(140px);
      opacity: 0.18;
    }
    .blob-1 { top: -200px; left: -100px; background: #38bdf8; }
    .blob-2 { top: 30%; right: -200px; background: #818cf8; }
    .blob-3 { bottom: -150px; left: 30%; background: #c084fc; }

    /* 通用容器 */
    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 24px;
      position: relative;
      z-index: 1;
    }

    /* 顶部导航 */
    header {
      position: sticky;
      top: 0;
      z-index: 100;
      background: rgba(9, 13, 22, 0.75);
      backdrop-filter: var(--glass-blur);
      border-bottom: 1px solid var(--border-subtle);
      transition: all 0.3s ease;
    }
    [data-theme="light"] header {
      background: rgba(255, 255, 255, 0.85);
    }
    .nav-inner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 70px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
      color: var(--text-main);
      font-weight: 700;
      font-size: 1.25rem;
    }
    .brand-logo {
      width: 36px;
      height: 36px;
      background: var(--primary-gradient);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-weight: 900;
      box-shadow: 0 4px 14px rgba(56, 189, 248, 0.4);
    }
    .nav-links {
      display: flex;
      gap: 24px;
      list-style: none;
    }
    .nav-links a {
      color: var(--text-muted);
      text-decoration: none;
      font-size: 0.95rem;
      font-weight: 500;
      transition: color 0.2s ease;
    }
    .nav-links a:hover {
      color: var(--primary);
    }
    .nav-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .theme-toggle {
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-subtle);
      color: var(--text-main);
      width: 40px;
      height: 40px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .theme-toggle:hover {
      border-color: var(--border-focus);
      transform: scale(1.05);
    }

    /* HERO 模块 */
    .hero {
      padding: 90px 0 60px;
      text-align: center;
    }
    .badge-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 16px;
      border-radius: 100px;
      background: rgba(56, 189, 248, 0.1);
      border: 1px solid rgba(56, 189, 248, 0.25);
      color: var(--primary);
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: 24px;
    }
    .hero h1 {
      font-size: 3.4rem;
      font-weight: 800;
      line-height: 1.15;
      letter-spacing: -0.02em;
      margin-bottom: 20px;
    }
    .gradient-text {
      background: var(--primary-gradient);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .hero-lead {
      max-width: 780px;
      margin: 0 auto 36px;
      font-size: 1.2rem;
      color: var(--text-muted);
      line-height: 1.7;
    }
    .hero-cta {
      display: flex;
      justify-content: center;
      gap: 16px;
      margin-bottom: 56px;
      flex-wrap: wrap;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 12px 28px;
      border-radius: var(--radius-md);
      font-size: 0.98rem;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
      transition: all 0.25s ease;
      border: none;
    }
    .btn-primary {
      background: var(--primary-gradient);
      color: #fff;
      box-shadow: 0 8px 24px rgba(56, 189, 248, 0.3);
    }
    .btn-primary:hover {
      box-shadow: 0 12px 30px rgba(56, 189, 248, 0.5);
      transform: translateY(-2px);
    }
    .btn-secondary {
      background: var(--bg-surface-elevated);
      color: var(--text-main);
      border: 1px solid var(--border-subtle);
    }
    .btn-secondary:hover {
      border-color: var(--border-focus);
      background: var(--bg-card-hover);
      transform: translateY(-2px);
    }

    /* 指标矩阵统计卡 */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 18px;
      margin-bottom: 60px;
    }
    .metric-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 24px 20px;
      text-align: left;
      backdrop-filter: var(--glass-blur);
      transition: all 0.3s ease;
    }
    .metric-card:hover {
      border-color: var(--border-focus);
      transform: translateY(-3px);
      box-shadow: var(--shadow-glow);
    }
    .metric-val {
      font-size: 2rem;
      font-weight: 800;
      color: var(--primary);
      margin-bottom: 6px;
      font-family: var(--font-code);
    }
    .metric-label {
      font-size: 0.95rem;
      font-weight: 600;
      color: var(--text-main);
      margin-bottom: 4px;
    }
    .metric-desc {
      font-size: 0.8rem;
      color: var(--text-muted);
      line-height: 1.4;
    }

    /* 区域标题通用 */
    .section-header {
      text-align: center;
      margin-bottom: 48px;
    }
    .section-tag {
      text-transform: uppercase;
      font-size: 0.8rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      color: var(--primary);
      margin-bottom: 8px;
      display: block;
    }
    .section-title {
      font-size: 2.2rem;
      font-weight: 800;
      margin-bottom: 12px;
    }
    .section-subtitle {
      color: var(--text-muted);
      max-width: 650px;
      margin: 0 auto;
      font-size: 1.05rem;
    }

    /* 三阶段状态机交互演示 */
    .stage-section {
      padding: 60px 0;
    }
    .stage-tabs {
      display: flex;
      justify-content: center;
      gap: 16px;
      margin-bottom: 30px;
      flex-wrap: wrap;
    }
    .stage-tab-btn {
      padding: 14px 28px;
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      color: var(--text-muted);
      font-weight: 600;
      font-size: 1rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 10px;
      transition: all 0.25s ease;
    }
    .stage-tab-btn.active {
      background: var(--primary-gradient);
      color: #fff;
      border-color: transparent;
      box-shadow: 0 6px 20px rgba(56, 189, 248, 0.35);
    }
    .stage-display-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-lg);
      padding: 36px;
      backdrop-filter: var(--glass-blur);
      box-shadow: var(--shadow-glow);
      display: grid;
      grid-template-columns: 1fr 1.1fr;
      gap: 36px;
      align-items: center;
    }
    .stage-detail h3 {
      font-size: 1.6rem;
      font-weight: 700;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .stage-badge {
      font-size: 0.75rem;
      padding: 4px 10px;
      border-radius: 6px;
      font-weight: 700;
      letter-spacing: 0.05em;
    }
    .stage-badge.explore { background: rgba(6, 182, 212, 0.2); color: var(--accent-cyan); }
    .stage-badge.modify { background: rgba(245, 158, 11, 0.2); color: var(--accent-amber); }
    .stage-badge.verify { background: rgba(16, 185, 129, 0.2); color: var(--accent-emerald); }

    .stage-detail p {
      color: var(--text-muted);
      margin-bottom: 20px;
      line-height: 1.6;
    }
    .stage-rules-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .stage-rules-list li {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      font-size: 0.92rem;
      color: var(--text-muted);
    }
    .rule-bullet {
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: rgba(56, 189, 248, 0.15);
      color: var(--primary);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 0.75rem;
      font-weight: 700;
      flex-shrink: 0;
      margin-top: 3px;
    }
    .stage-code-preview {
      background: #05070d;
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: var(--radius-md);
      overflow: hidden;
      font-family: var(--font-code);
      font-size: 0.88rem;
    }
    .code-titlebar {
      background: #0f1522;
      padding: 10px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }
    .code-dots {
      display: flex;
      gap: 6px;
    }
    .code-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }
    .code-dot.red { background: #ef4444; }
    .code-dot.yellow { background: #f59e0b; }
    .code-dot.green { background: #10b981; }
    .code-content {
      padding: 18px;
      color: #cbd5e1;
      white-space: pre;
      line-height: 1.6;
      overflow-x: auto;
    }
    .code-hl-blue { color: #38bdf8; font-weight: 600; }
    .code-hl-green { color: #4ade80; }
    .code-hl-purple { color: #c084fc; }
    .code-hl-yellow { color: #fbbf24; }
    .code-hl-comment { color: #64748b; font-style: italic; }

    /* 六大核心架构特性 */
    .features-section {
      padding: 80px 0;
    }
    .features-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 24px;
    }
    .feature-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 30px 24px;
      backdrop-filter: var(--glass-blur);
      transition: all 0.3s ease;
      display: flex;
      flex-direction: column;
    }
    .feature-card:hover {
      border-color: var(--border-focus);
      transform: translateY(-4px);
      box-shadow: var(--shadow-glow);
    }
    .feature-icon-wrapper {
      width: 52px;
      height: 52px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 20px;
      color: #fff;
    }
    .feature-card h3 {
      font-size: 1.25rem;
      font-weight: 700;
      margin-bottom: 10px;
    }
    .feature-card p {
      color: var(--text-muted);
      font-size: 0.92rem;
      line-height: 1.65;
      margin-bottom: 16px;
      flex-grow: 1;
    }
    .feature-tags {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .feature-tag-chip {
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-subtle);
      font-size: 0.75rem;
      padding: 3px 8px;
      border-radius: 6px;
      color: var(--text-faint);
      font-family: var(--font-code);
    }

    /* 内置工具矩阵 */
    .tools-section {
      padding: 80px 0;
    }
    .tools-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 20px;
    }
    .tool-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 24px;
      backdrop-filter: var(--glass-blur);
      display: flex;
      gap: 18px;
      transition: all 0.25s ease;
    }
    .tool-card:hover {
      border-color: var(--border-focus);
      background: var(--bg-card-hover);
    }
    .tool-icon {
      width: 44px;
      height: 44px;
      border-radius: 10px;
      background: rgba(56, 189, 248, 0.1);
      border: 1px solid rgba(56, 189, 248, 0.2);
      color: var(--primary);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .tool-body {
      flex: 1;
    }
    .tool-header-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 6px;
    }
    .tool-name {
      font-family: var(--font-code);
      font-size: 1.05rem;
      font-weight: 700;
      color: var(--primary);
    }
    .tool-guard {
      font-size: 0.75rem;
      padding: 2px 8px;
      border-radius: 4px;
      background: rgba(244, 63, 94, 0.1);
      color: var(--accent-rose);
      border: 1px solid rgba(244, 63, 94, 0.25);
    }
    .tool-desc {
      font-size: 0.88rem;
      color: var(--text-muted);
      line-height: 1.55;
      margin-bottom: 8px;
    }
    .tool-spec {
      font-size: 0.8rem;
      color: var(--text-faint);
    }
    .tool-spec strong {
      color: var(--text-muted);
    }

    /* 架构时序流程图 */
    .pipeline-section {
      padding: 80px 0;
    }
    .pipeline-box {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-lg);
      padding: 40px;
      backdrop-filter: var(--glass-blur);
    }
    .pipeline-steps {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 12px;
      position: relative;
    }
    .step-item {
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 20px 16px;
      text-align: center;
      position: relative;
    }
    .step-num {
      width: 28px;
      height: 28px;
      background: var(--primary-gradient);
      color: #fff;
      font-weight: 700;
      font-size: 0.85rem;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 12px;
    }
    .step-title {
      font-size: 0.95rem;
      font-weight: 700;
      margin-bottom: 6px;
    }
    .step-desc {
      font-size: 0.78rem;
      color: var(--text-muted);
      line-height: 1.4;
    }

    /* 终端指令速查 Cheatsheet */
    .cmd-section {
      padding: 60px 0 100px;
    }
    .cmd-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
    }
    .cmd-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 18px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .cmd-left code {
      font-family: var(--font-code);
      font-size: 1rem;
      color: var(--primary);
      font-weight: 600;
    }
    .cmd-left p {
      font-size: 0.82rem;
      color: var(--text-muted);
      margin-top: 4px;
    }
    .copy-btn {
      background: transparent;
      border: 1px solid var(--border-subtle);
      color: var(--text-faint);
      width: 34px;
      height: 34px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: all 0.2s;
    }
    .copy-btn:hover {
      border-color: var(--border-focus);
      color: var(--primary);
    }

    /* 底部声明 */
    footer {
      border-top: 1px solid var(--border-subtle);
      padding: 40px 0;
      background: var(--bg-surface);
      text-align: center;
    }
    .footer-content {
      color: var(--text-faint);
      font-size: 0.88rem;
    }
    .footer-content a {
      color: var(--primary);
      text-decoration: none;
    }

    /* Toast 提示 */
    .toast {
      position: fixed;
      bottom: 30px;
      right: 30px;
      background: #10b981;
      color: #fff;
      padding: 10px 20px;
      border-radius: 8px;
      font-size: 0.9rem;
      font-weight: 600;
      box-shadow: 0 8px 20px rgba(16, 185, 129, 0.4);
      opacity: 0;
      transform: translateY(20px);
      transition: all 0.3s ease;
      z-index: 9999;
      pointer-events: none;
    }
    .toast.show {
      opacity: 1;
      transform: translateY(0);
    }

    /* 响应式调整 */
    @media (max-width: 1024px) {
      .metrics-grid { grid-template-columns: repeat(2, 1fr); }
      .features-grid { grid-template-columns: repeat(2, 1fr); }
      .stage-display-card { grid-template-columns: 1fr; }
      .pipeline-steps { grid-template-columns: 1fr; }
      .cmd-grid { grid-template-columns: repeat(2, 1fr); }
    }
    @media (max-width: 768px) {
      .hero h1 { font-size: 2.4rem; }
      .metrics-grid { grid-template-columns: 1fr; }
      .features-grid { grid-template-columns: 1fr; }
      .tools-grid { grid-template-columns: 1fr; }
      .cmd-grid { grid-template-columns: 1fr; }
      .nav-links { display: none; }
    }
  </style>
</head>
<body>

  <!-- 背景流光 -->
  <div class="bg-glow-container">
    <div class="glow-blob blob-1"></div>
    <div class="glow-blob blob-2"></div>
    <div class="glow-blob blob-3"></div>
  </div>

  <!-- 顶部导航 -->
  <header>
    <div class="container nav-inner">
      <a href="#" class="brand">
        <div class="brand-logo">S</div>
        <span>Super-Harnes</span>
      </a>
      <ul class="nav-links">
        <li><a href="#stages">三阶段状态机</a></li>
        <li><a href="#features">核心架构柱石</a></li>
        <li><a href="#tools">内置工程工具</a></li>
        <li><a href="#pipeline">时序流转</a></li>
        <li><a href="#cheatsheet">常用指令</a></li>
      </ul>
      <div class="nav-actions">
        <button class="theme-toggle" id="themeToggle" title="切换深色/浅色模式">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="5"></circle>
            <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"></path>
          </svg>
        </button>
      </div>
    </div>
  </header>

  <!-- HERO 区域 -->
  <section class="hero">
    <div class="container">
      <div class="badge-pill">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
        工业级自主代码工程 AI 智能体 (Autonomous Coding Agent)
      </div>
      <h1>
        赋能真工程的自主推理中枢<br>
        <span class="gradient-text">Super-Harnes 智能体</span>
      </h1>
      <p class="hero-lead">
        面向工业级真实软件项目的下一代编程智能体。以 <strong>ReAct 多步闭环决策</strong> 为核心，集成了 <strong>200K~500K 弹性滑窗分账账本</strong>、<strong>三阶段任务状态机</strong>、<strong>物理快照原子回滚</strong> 与 <strong>零端口 MCP 外部扩展</strong>。
      </p>
      <div class="hero-cta">
        <a href="#stages" class="btn btn-primary">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polygon points="10 8 16 12 10 16 10 8"></polygon></svg>
          体验状态机交互
        </a>
        <a href="#features" class="btn btn-secondary">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>
          查阅技术架构
        </a>
      </div>

      <!-- 4 数量化指标 -->
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-val">200K~500K</div>
          <div class="metric-label">弹性硬预算滑窗</div>
          <div class="metric-desc">专款专用财务账本，TurnChunk 原子成对绑定，杜绝孤儿调用 400 校验异常。</div>
        </div>
        <div class="metric-card">
          <div class="metric-val">3-Stage</div>
          <div class="metric-label">动态任务状态机</div>
          <div class="metric-desc">EXPLORE &rarr; MODIFY &rarr; VERIFY，注意力置顶加权，驱动模型自省收敛。</div>
        </div>
        <div class="metric-card">
          <div class="metric-val">0 Ports</div>
          <div class="metric-label">零端口 MCP 扩展</div>
          <div class="metric-desc">基于 JSON-RPC 2.0 Stdio 内存管道通信，内核 Job Object 托管防止僵尸进程。</div>
        </div>
        <div class="metric-card">
          <div class="metric-val">100%</div>
          <div class="metric-label">物理快照原子事务</div>
          <div class="metric-desc">写前 Shadow Snapshot 备份，多文件补丁全成全败，真实物理级 /undo 还原。</div>
        </div>
      </div>
    </div>
  </section>

  <!-- 阶段状态机互动演示 -->
  <section id="stages" class="stage-section">
    <div class="container">
      <div class="section-header">
        <span class="section-tag">State Machine Architecture</span>
        <h2 class="section-title">三阶段状态机与注意力加权</h2>
        <p class="section-subtitle">打破无状态 LLM 的盲目试错，通过工程状态机驱动智能体按严谨 SOP 演进</p>
      </div>

      <div class="stage-tabs">
        <button class="stage-tab-btn active" onclick="switchStage('explore')">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          1. EXPLORE 探索排查态
        </button>
        <button class="stage-tab-btn" onclick="switchStage('modify')">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
          2. MODIFY 编码实施态
        </button>
        <button class="stage-tab-btn" onclick="switchStage('verify')">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
          3. VERIFY 验证闭环态
        </button>
      </div>

      <div class="stage-display-card" id="stageCard">
        <!-- 动态 JS 填充内容 -->
      </div>
    </div>
  </section>

  <!-- 六大核心技术特性 -->
  <section id="features" class="features-section">
    <div class="container">
      <div class="section-header">
        <span class="section-tag">Core Pillars</span>
        <h2 class="section-title">工业级工程特性矩阵</h2>
        <p class="section-subtitle">专为真实工程痛点打造，绝非简单玩具级 API 包装</p>
      </div>

      <div class="features-grid">
        <!-- 卡片 1 -->
        <div class="feature-card">
          <div class="feature-icon-wrapper" style="background: linear-gradient(135deg, #06b6d4, #3b82f6);">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
          </div>
          <h3>任务感知型 ReAct 中枢</h3>
          <p>严格执行 Thought &rarr; Action &rarr; Observation 决策循环。内置死循环与停滞拦截器 (LoopDetector)，自动识别单工具复读、震荡循环与连续报错，先出黄牌反思，再出红牌强制截断收敛汇报。</p>
          <div class="feature-tags">
            <span class="feature-tag-chip">LoopDetector</span>
            <span class="feature-tag-chip">黄牌反思</span>
            <span class="feature-tag-chip">红牌收敛</span>
          </div>
        </div>

        <!-- 卡片 2 -->
        <div class="feature-card">
          <div class="feature-icon-wrapper" style="background: linear-gradient(135deg, #8b5cf6, #ec4899);">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect><rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect><line x1="6" y1="6" x2="6.01" y2="6"></line><line x1="6" y1="18" x2="6.01" y2="18"></line></svg>
          </div>
          <h3>200K~500K 弹性滑窗账本</h3>
          <p>划定专款专用保护区：系统提示词 (4k)、Schema (6k)、工作记忆 (6k)、输出预留区 (8k)。支持 200k~500k 自动跃迁，配备三段式水位控制（绿区直通、黄区倒序滑窗、红区历史增量压缩摘要）。</p>
          <div class="feature-tags">
            <span class="feature-tag-chip">BudgetLedger</span>
            <span class="feature-tag-chip">TurnChunk</span>
            <span class="feature-tag-chip">防抖缩容</span>
          </div>
        </div>

        <!-- 卡片 3 -->
        <div class="feature-card">
          <div class="feature-icon-wrapper" style="background: linear-gradient(135deg, #10b981, #06b6d4);">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
          </div>
          <h3>物理快照与原子回滚</h3>
          <p>修改前毫秒级 Shadow Snapshot 磁盘快照备份。多文件打补丁具备事务原子性，任一文件语法自检或替换失败立即全量回退。输入 <code>/undo</code> 命令不仅撤销对话，同时在物理磁盘上原样还原文件。</p>
          <div class="feature-tags">
            <span class="feature-tag-chip">ShadowSnapshot</span>
            <span class="feature-tag-chip">PatchTransaction</span>
            <span class="feature-tag-chip">/undo 还原</span>
          </div>
        </div>

        <!-- 卡片 4 -->
        <div class="feature-card">
          <div class="feature-icon-wrapper" style="background: linear-gradient(135deg, #f59e0b, #ef4444);">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
          </div>
          <h3>0 端口 MCP 协议扩展</h3>
          <p>全面兼容 Model Context Protocol 规范。采用纯内存 JSON-RPC 2.0 Stdio 标准流管道，<strong>完全不监听占用本地网络端口</strong>。在 Windows 下通过 Job Object 绑定进程树，父进程崩溃时子进程连带注销，拒绝后台残留。</p>
          <div class="feature-tags">
            <span class="feature-tag-chip">JSON-RPC 2.0</span>
            <span class="feature-tag-chip">Stdio IPC</span>
            <span class="feature-tag-chip">Job Object</span>
          </div>
        </div>

        <!-- 卡片 5 -->
        <div class="feature-card">
          <div class="feature-icon-wrapper" style="background: linear-gradient(135deg, #6366f1, #a855f7);">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
          </div>
          <h3>原生 Skills 专家技能生态</h3>
          <p>遵循业界标准 <code>SKILL.md</code> 规范，兼容 Claude Code / OpenAI 技能格式。预置设计、导读、诊断与领域建模等专家 SOP。按需动态加载完整工作流规约，让模型瞬间拥有架构师与资深排查专家的专业能力。</p>
          <div class="feature-tags">
            <span class="feature-tag-chip">SKILL.md 兼容</span>
            <span class="feature-tag-chip">按需加载</span>
            <span class="feature-tag-chip">SOP 工作流</span>
          </div>
        </div>

        <!-- 卡片 6 -->
        <div class="feature-card">
          <div class="feature-icon-wrapper" style="background: linear-gradient(135deg, #0ea5e9, #22c55e);">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          </div>
          <h3>多会话分箱与跨会话总线</h3>
          <p>支持 <code>/sessions</code> 物理隔离与多会话自由切换。全局画像跨项目永久沉淀开发者编码喜好；项目级共享总线 (<code>ProjectState</code>) 跨会话共享改动拓扑与排查结论，团队协同开发零碰撞。</p>
          <div class="feature-tags">
            <span class="feature-tag-chip">GlobalMemory</span>
            <span class="feature-tag-chip">ProjectState</span>
            <span class="feature-tag-chip">独立物理分箱</span>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- 内置工程工具矩阵 -->
  <section id="tools" class="tools-section">
    <div class="container">
      <div class="section-header">
        <span class="section-tag">Engineered Toolset</span>
        <h2 class="section-title">内置工业级专用工具箱</h2>
        <p class="section-subtitle">专为消除大模型幻觉与上下文爆仓而打造的高精度工具体系</p>
      </div>

      <div class="tools-grid">
        <!-- view_file_outline -->
        <div class="tool-card">
          <div class="tool-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
          </div>
          <div class="tool-body">
            <div class="tool-header-row">
              <span class="tool-name">view_file_outline</span>
              <span class="tool-guard">大纲先行·防爆</span>
            </div>
            <p class="tool-desc">基于 AST 语法树快速提取类、函数、参数签名及所在行号，无需通读几千行源码即可建立架构认知。</p>
            <div class="tool-spec"><strong>硬性纪律：</strong>严禁盲目直接从第 1 行通读 >150 行长代码文件。</div>
          </div>
        </div>

        <!-- apply_patch -->
        <div class="tool-card">
          <div class="tool-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>
          </div>
          <div class="tool-body">
            <div class="tool-header-row">
              <span class="tool-name">apply_patch</span>
              <span class="tool-guard">原子事务·AST自检</span>
            </div>
            <p class="tool-desc">确定性 SEARCH/REPLACE 块精准补丁修改。自动剥离行号前缀，并在落盘前执行 AST 语法自检与 Unified Diff 渲染。</p>
            <div class="tool-spec"><strong>硬性纪律：</strong>禁止为微调几行代码而全盘覆写原文件；失败全自动回滚。</div>
          </div>
        </div>

        <!-- read_file -->
        <div class="tool-card">
          <div class="tool-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
          </div>
          <div class="tool-body">
            <div class="tool-header-row">
              <span class="tool-name">read_file</span>
              <span class="tool-guard">自适应编码·切片</span>
            </div>
            <p class="tool-desc">支持 UTF-8、GBK 自适应编码识别，具备行号范围 (start_line/max_lines) 安全分页读取与字符溢出熔断机制。</p>
            <div class="tool-spec"><strong>硬性纪律：</strong>单次读取上限不超过 1000 行，禁止触碰 .env 敏感配置。</div>
          </div>
        </div>

        <!-- run_shell -->
        <div class="tool-card">
          <div class="tool-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
          </div>
          <div class="tool-body">
            <div class="tool-header-row">
              <span class="tool-name">run_shell</span>
              <span class="tool-guard">防逃逸·日志转储</span>
            </div>
            <p class="tool-desc">安全终端执行器。支持双模审批 (AUTO/ASK)，复合命令链切分审计防范注入逃逸，超长日志自动落盘转储。</p>
            <div class="tool-spec"><strong>硬性纪律：</strong>严禁使用终端 cat/grep 代替内置专用工具；高危命令需人工确认。</div>
          </div>
        </div>

        <!-- grep_text -->
        <div class="tool-card">
          <div class="tool-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          </div>
          <div class="tool-body">
            <div class="tool-header-row">
              <span class="tool-name">grep_text</span>
              <span class="tool-guard">毫秒全文·忽略构建</span>
            </div>
            <p class="tool-desc">底层优先调用 Git Grep 引擎，毫秒级响应并严格遵守 .gitignore，自动过滤二进制文件与产物。</p>
            <div class="tool-spec"><strong>应用场景：</strong>快速排查变量引用、类定义与控制台报错堆栈。</div>
          </div>
        </div>

        <!-- find_by_name -->
        <div class="tool-card">
          <div class="tool-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
          </div>
          <div class="tool-body">
            <div class="tool-header-row">
              <span class="tool-name">find_by_name</span>
              <span class="tool-guard">Git加速·剪枝剪析</span>
            </div>
            <p class="tool-desc">文件名通配检索。智能集成 Git 索引，自动跳过 node_modules、.git 等深层庞大目录，避免无效 I/O 阻塞。</p>
            <div class="tool-spec"><strong>应用场景：</strong>探索未知模块路径与配置文件分布。</div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- 架构时序流程 -->
  <section id="pipeline" class="pipeline-section">
    <div class="container">
      <div class="section-header">
        <span class="section-tag">Execution Workflow</span>
        <h2 class="section-title">端到端自主闭环流转时序</h2>
        <p class="section-subtitle">从用户输入到真实磁盘代码交付的完整全链路保障机制</p>
      </div>

      <div class="pipeline-box">
        <div class="pipeline-steps">
          <div class="step-item">
            <div class="step-num">1</div>
            <div class="step-title">上下文装配</div>
            <div class="step-desc">注入系统提示词、全局用户记忆、工作记忆与弹性滑窗预算</div>
          </div>
          <div class="step-item">
            <div class="step-num">2</div>
            <div class="step-title">ReAct 推理</div>
            <div class="step-desc">阶段状态机加权工具 Schema，模型输出 Thought 与 Action</div>
          </div>
          <div class="step-item">
            <div class="step-num">3</div>
            <div class="step-title">熔断与审批</div>
            <div class="step-desc">死循环侦测器自检，高危 Shell 命令触发人工或白名单审计</div>
          </div>
          <div class="step-item">
            <div class="step-num">4</div>
            <div class="step-title">原子打补丁</div>
            <div class="step-desc">毫秒级快照备份，确定性 SEARCH/REPLACE 与语法树完整性自检</div>
          </div>
          <div class="step-item">
            <div class="step-num">5</div>
            <div class="step-title">闭环与收敛</div>
            <div class="step-desc">审查 git diff，自动运行单元测试确保零回归，收拢输出交付</div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- 常用指令 Cheatsheet -->
  <section id="cheatsheet" class="cmd-section">
    <div class="container">
      <div class="section-header">
        <span class="section-tag">Commands & Cheatsheet</span>
        <h2 class="section-title">快捷指令与常用操作</h2>
        <p class="section-subtitle">终端与桌面端均可使用的核心控制指令</p>
      </div>

      <div class="cmd-grid">
        <div class="cmd-card">
          <div class="cmd-left">
            <code>/undo</code>
            <p>真实物理回滚：还原磁盘修改，删除新建文件</p>
          </div>
          <button class="copy-btn" onclick="copyText('/undo')" title="复制">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          </button>
        </div>

        <div class="cmd-card">
          <div class="cmd-left">
            <code>/sessions</code>
            <p>列出所有历史工程会话，查看物理分箱归档</p>
          </div>
          <button class="copy-btn" onclick="copyText('/sessions')" title="复制">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          </button>
        </div>

        <div class="cmd-card">
          <div class="cmd-left">
            <code>/skills</code>
            <p>展示工作区与全局已挂载的领域专家技能列表</p>
          </div>
          <button class="copy-btn" onclick="copyText('/skills')" title="复制">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          </button>
        </div>

        <div class="cmd-card">
          <div class="cmd-left">
            <code>/remember &lt;偏好&gt;</code>
            <p>永久沉淀全局用户偏好至 global_memory.json</p>
          </div>
          <button class="copy-btn" onclick="copyText('/remember ')" title="复制">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          </button>
        </div>

        <div class="cmd-card">
          <div class="cmd-left">
            <code>/switch &lt;id&gt;</code>
            <p>零重启秒级切换到指定历史会话上下文</p>
          </div>
          <button class="copy-btn" onclick="copyText('/switch ')" title="复制">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          </button>
        </div>

        <div class="cmd-card">
          <div class="cmd-left">
            <code>/session new</code>
            <p>重置并创建全新干净的独立会话沙盒</p>
          </div>
          <button class="copy-btn" onclick="copyText('/session new')" title="复制">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          </button>
        </div>
      </div>
    </div>
  </section>

  <!-- 底部 Footer -->
  <footer>
    <div class="container footer-content">
      <p>Super-Harnes 🚀 工业级自主代码工程 AI Agent · 单文件纯 HTML 离线介绍页</p>
      <p style="margin-top: 8px; font-size: 0.8rem; color: var(--text-faint);">
        系统架构：ReAct Loop · 弹性硬预算滑窗 · 状态机加权 · 零端口 MCP · 快照原子回滚
      </p>
    </div>
  </footer>

  <!-- Toast 提示 -->
  <div class="toast" id="toast">已成功复制到剪贴板！</div>

  <script>
    // 阶段状态机数据
    const stageData = {
      explore: {
        title: "EXPLORE · 探索排查态",
        badge: "EXPLORE",
        badgeClass: "explore",
        desc: "刚接入任务或遭遇新问题时的初识状态。核心目标是搜集事实证据、建立架构认知并锁定缺陷根因，坚决禁止在此阶段贸然修改代码。",
        rules: [
          "优先调用 view_file_outline 提取类与函数骨架，严禁通读超 150 行未知文件",
          "并发调用 grep_text 或 find_by_name 全局定位符号与文件路径",
          "锁定行号范围后，使用 read_file 进行高精度切片阅读",
          "只有搜集到充分上下文后，才允许向 MODIFY 阶段跃迁"
        ],
        codeSnippet: `// [StageManager] EXPLORE 阶段工具权限与注意力加权
stage: "EXPLORE"
tools_priority: [
  "view_file_outline", // 置顶权重: 1.0 (大纲先行)
  "read_file",          // 置顶权重: 0.9 (定向切片)
  "grep_text",          // 置顶权重: 0.8 (精准检索)
  "find_by_name"        // 置顶权重: 0.8 (快速定位)
]
guardrail: "严禁在未定位代码前执行修改；禁止盲目大文件全盘通读"`
      },
      modify: {
        title: "MODIFY · 编码实施态",
        badge: "MODIFY",
        badgeClass: "modify",
        desc: "已准确定位问题与代码位置，进入实施阶段。核心原则是最小侵入性、原子性修改，并在修改前自动触发 Shadow Snapshot 磁盘快照备份。",
        rules: [
          "严格使用 apply_patch 进行确定性 SEARCH/REPLACE 局部补丁替换",
          "若涉及全新文件创建，必须进行语法自检与写前备份",
          "修改前自动生成毫秒级物理影子快照，确保随时可无损撤销",
          "补丁打入成功后，状态机自动迁移至 VERIFY 阶段"
        ],
        codeSnippet: `// [StageManager] MODIFY 阶段工具权限与注意力加权
stage: "MODIFY"
tools_priority: [
  "apply_patch", // 置顶权重: 1.0 (最小侵入打补丁)
  "write_file"   // 置顶权重: 0.7 (仅限新建独立模块)
]
transaction: {
  snapshot_before_write: true, // 磁盘写前快照
  ast_syntax_check: true,      // AST 语法自检诊断
  atomic_rollback_on_fail: true // 补丁中途失败全自动回滚
}`
      },
      verify: {
        title: "VERIFY · 验证闭环态",
        badge: "VERIFY",
        badgeClass: "verify",
        desc: "代码修改已完成，进入严格的工程闭环验证。必须审查差异、运行测试套件，确认不仅修复了原问题，且未引入任何回归破坏。",
        rules: [
          "必须调用 run_shell(command='git diff') 全面审查代码修改细节",
          "运行项目测试用例（如 pytest / unittest / npm test）进行回归验证",
          "若测试不通过，可依靠快照还原并微调，严禁带病交付",
          "验证无误后，收敛输出清晰、结构化、包含具体文件行号的最终报告"
        ],
        codeSnippet: `// [StageManager] VERIFY 阶段工具权限与注意力加权
stage: "VERIFY"
tools_priority: [
  "run_shell: git diff", // 置顶权重: 1.0 (改动差异审查)
  "run_shell: pytest",   // 置顶权重: 0.95 (自动化测试验证)
  "read_file"            // 置顶权重: 0.6 (复查修改后代码)
]
completion_gate: {
  diff_reviewed: true,
  tests_passed: true,
  zero_regression_confirmed: true
}`
      }
    };

    // 切换状态机展示
    function switchStage(stageKey) {
      const data = stageData[stageKey];
      if (!data) return;

      // 更新按钮激活状态
      const buttons = document.querySelectorAll('.stage-tab-btn');
      buttons.forEach(btn => btn.classList.remove('active'));
      const activeBtn = Array.from(buttons).find(b => b.textContent.toLowerCase().includes(stageKey));
      if (activeBtn) activeBtn.classList.add('active');

      // 更新卡片内容
      const card = document.getElementById('stageCard');
      card.innerHTML = `
        <div class="stage-detail">
          <h3>
            ${data.title}
            <span class="stage-badge ${data.badgeClass}">${data.badge}</span>
          </h3>
          <p>${data.desc}</p>
          <ul class="stage-rules-list">
            ${data.rules.map(rule => `
              <li>
                <span class="rule-bullet">&check;</span>
                <span>${rule}</span>
              </li>
            `).join('')}
          </ul>
        </div>
        <div class="stage-code-preview">
          <div class="code-titlebar">
            <span style="font-size: 0.78rem; color: #94a3b8; font-family: monospace;">StagePolicy.json</span>
            <div class="code-dots">
              <div class="code-dot red"></div>
              <div class="code-dot yellow"></div>
              <div class="code-dot green"></div>
            </div>
          </div>
          <div class="code-content">${escapeHtml(data.codeSnippet)}</div>
        </div>
      `;
    }

    function escapeHtml(str) {
      return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // 主题切换
    const themeToggle = document.getElementById('themeToggle');
    let currentTheme = localStorage.getItem('super_theme') || 'dark';

    function applyTheme(theme) {
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('super_theme', theme);
    }
    applyTheme(currentTheme);

    themeToggle.addEventListener('click', () => {
      currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
      applyTheme(currentTheme);
    });

    // 复制功能与 Toast
    function copyText(text) {
      navigator.clipboard.writeText(text).then(() => {
        const toast = document.getElementById('toast');
        toast.textContent = `已复制指令: ${text}`;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 2200);
      }).catch(() => {
        alert("复制失败，请手动选择复制");
      });
    }

    // 初始化第一阶段
    switchStage('explore');
  </script>
</body>
</html>
"""

def main():
    desktop_dir = os.path.expanduser('~/Desktop')
    out_file = os.path.join(desktop_dir, 'Super智能体介绍.html')
    
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(HTML_CONTENT)
    
    file_size_kb = os.path.getsize(out_file) / 1024
    print(f"Successfully generated HTML introduction file to desktop!")
    print(f"Path: {out_file}")
    print(f"Size: {file_size_kb:.2f} KB")

if __name__ == '__main__':
    main()
