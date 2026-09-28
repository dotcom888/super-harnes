# Super-Harnes 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](scripts/run_checks.py)

> **Super-Harnes** 是一款专为真实软件工程排查、补丁修改与测试设计的轻量级、企业级安全代码 AI Agent。
> 采用 **ReAct (Reasoning + Acting)** 自主推理决策闭环，原生内置 **24K 动态硬预算滑动窗口**、**原子轮次持久化记忆**、**四重权限防御沙箱** 以及基于 Anthropic **MCP (Model Context Protocol)** 的外部进程扩展协议。

---

## 🌟 核心特性与架构亮点

### 1. 🧠 纯粹且高效的 ReAct 决策引擎
- **全自主推理**：按照 `Thought -> Action -> Observation -> Final Answer` 循环推进。
- **智能收敛与防死循环熔断**：步数超限或检测到重复调用循环时自动触发安全收敛，防止 Token 无序浪费。

### 2. 🛡️ 工业级四重安全沙箱 (Security Sandbox)
- **沙箱路径隔离**：通过 `WORKSPACE_ROOT` 断言，严禁跨盘符、符号链接及 `../` 路径穿越越界。
- **高危命令防御**：命令前置策略引擎 (`CommandPolicy`)，阻断破坏性命令（如 `rm -rf`、`format`、隐式下载脚本等）。
- **敏感资产防窥探**：严格屏蔽读取 `.env`、`id_rsa`、私钥及自身核心防护模块代码。
- **Human-in-the-Loop 人工审批**：敏感修改类命令支持终端实时弹窗询问 `[y/n/a]`。

### 3. 💾 24,000 Tokens 硬预算滑动窗口与记忆中枢
- **专款专用财务账本**：将 24K 预算严格划分为系统区、工具区、状态区、历史滑窗（15k）与大输出预留区（3k），杜绝长对话挤占模型输出空间。
- **原子轮次成对绑定 (`TurnChunk`)**：将每次调用的提问、工具与结果打包进不可分割的原子块，从数据结构层面彻底杜绝 `tool_calls` 孤儿导致的 OpenAI HTTP 400 校验报错。
- **永久锁定工作记忆 (`WorkingMemory`)**：自动感知已读代码范围、已修改文件路径及最新测试状态，永久置顶锁定。
- **防抖历史排查纪要 (`ContextSummarizer`)**：超过 75% 红区水位且满足三维防抖门槛时，自动增量生成带轮次区间锚点（`#1 ~ #8`）的高密度摘要。

### 4. 🔌 MCP (Model Context Protocol) 外部进程扩展
- **标准协议支持**：基于 JSON-RPC 2.0 Stdio（标准流管道 IPC）运行，通信全在内存管道中进行，**完全不占用任何本地网络端口（0 端口占用）**。
- **命名空间隔离与内核托管**：通过 `mcp__{server}__{tool}` 隔离前缀消除工具命名冲突，子进程绑定至操作系统内核级 Job Object，退出时全自动垃圾回收，无僵尸进程残留。

### 5. 💻 现代化终端 TUI 交互体验
- 基于 `prompt_toolkit` 与 `rich` 构建的高颜值终端界面，支持流式思考打字机输出、实时 Token 水位柱状指示条、命令历史补全与多轮控制指令。

---

## 🏗️ 架构流转时序

```text
               ┌───────────────────────────────┐
               │    用户输入 (User Prompt)      │
               └──────────────┬────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │ 1. 上下文组装与滑动窗口 (ContextManager)      │
        │    - 注入不可变 System Prompt                │
        │    - 注入永久锁定保留的 WorkingMemory        │
        │    - 倒序装入活跃轮次 (上限 15,000 Tokens)   │
        └─────────────────────┬───────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │ 2. 调用大模型进行推理决策 (LLM Completion)    │
        └──────────────┬──────────────────────────────┘
                       │
             ┌─────────┴─────────┐
             │ 是否包含工具调用? │
             └─────────┬─────────┘
        Yes            │            No (任务收敛达成)
   ┌───────────────────┘            └────────────────────┐
   ▼                                                     ▼
┌───────────────────────────────┐        ┌───────────────────────────────┐
│ 3. ToolExecutor 统一调度分发  │        │ 5. 生成最终结论 (Final Answer)│
│  - 本地文件/搜索: 沙箱校验    │        │  - 将答复写入当前轮次         │
│  - Shell命令: 交互审批/超时强杀│        │  - 增量落盘至 history/*.jsonl │
│  - MCP工具: Stdio管道协议代理 │        │  - 终端流式呈现给用户         │
└──────────────┬────────────────┘        └───────────────────────────────┘
               │
               ▼
┌───────────────────────────────┐
│ 4. 观察结果回填 (Observation) │
│  - 更新 WorkingMemory 感知状态 │
│  - 成对装配结果并进入下一步思考│
└───────────────────────────────┘
```

---

## 📁 目录结构与模块说明

```text
super-harnes/
│
├── core/                        # 【认知与决策中枢】ReAct 纯推理循环与提示词
├── cli/                         # 【控制台交互】REPL 界面、流式渲染与快捷命令处理
├── context/                     # 【记忆中枢】24K 硬预算滑动窗口、原子轮次、防抖摘要
├── tools/                       # 【工具体系】
│   ├── framework/               # -- 注册中心 (Registry)、执行调度 (Executor)、安全策略 (Policies)
│   └── builtin/                 # -- 原生内置安全工具 (file_tools, search_tools, patch_tool, shell_tool)
├── mcp/                         # 【MCP 扩展】标准 JSON-RPC 2.0 Stdio 客户端、管理器与示例服务
├── skills/                      # 【技能体系】模块化专业场景技能加载与解析
├── config/                      # 【配置管理】环境变量映射、路径规范与 mcp_servers.json
├── scripts/                     # 【运维脚本】一键自检 run_checks.py、免激活启动 super.cmd/super.ps1
├── tests/                       # 【测试套件】涵盖滑窗算法、MCP RPC 通信、沙箱策略等全量测试
│
├── .env.example                 # 环境变量模板示例
├── .gitignore                   # 工业级 Git 忽略规则
├── requirements.txt             # 核心依赖清单
├── LICENSE                      # MIT 开源许可证
└── main.py                      # 【系统统一标准启动入口】
```

---

## 🚀 快速上手

### 1. 环境克隆与安装
确保安装了 Python 3.10 及以上版本：
```bash
git clone https://github.com/your-username/super-harnes.git
cd super-harnes

# 推荐创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装必要依赖
pip install -r requirements.txt
```

### 2. 配置大模型 API
复制环境变量模板：
```bash
cp .env.example .env  # Windows: copy .env.example .env
```
编辑 `.env` 填入您的模型参数（默认开箱即用支持 DeepSeek，同时兼容通义千问、智谱 GLM、Kimi、OpenAI 等标准兼容接口）：
```ini
LLM_API_KEY=your_actual_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
APPROVAL_MODE=auto
```

### 3. 运行自动化自检测试
在正式运行前，一键执行全量测试套件：
```bash
python scripts/run_checks.py
```

### 4. 启动交互式 Agent
```bash
python main.py
```
*(Windows 用户也可直接双击运行 `.\scripts\super.cmd` 或在 PowerShell 中执行 `.\scripts\super.ps1`)*

---

## 🕹️ 终端控制指令

在交互控制台中，可随时输入以下斜杠命令控制 Agent：
* `/status` 或 `/memory`：实时查看当前工作区感知记忆与 MCP 挂载服务。
* `/restore`：从 `history/default.jsonl` 恢复先前的长程排查会话。
* `/undo`：一键回滚最近一轮问答与修改记录。
* `/reset` 或 `/new`：清空内存上下文，开启全新的排查目标。
* `/history`：查看历史轮次耗费的 Token 预算概要。
* `/help`：查看控制台帮助文档。
* `quit` 或 `exit`：优雅退出程序并销毁所有外部子进程。

---

## 🤝 贡献与反馈
欢迎提交 Issue 和 Pull Request！
在提交 PR 之前，请确保运行 `python scripts/run_checks.py` 并且所有单元测试均能通过。

---

## 📄 开源许可证
本项目基于 [MIT License](LICENSE) 开源。
