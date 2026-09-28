# Super-Harnes 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-145%20passed-brightgreen.svg)](scripts/run_checks.py)
[![Context](https://img.shields.io/badge/Context-200K%20~%20500K%20Elastic-orange.svg)](#2-200k--500k-弹性硬预算滑动窗口与分账账本)
[![Protocol](https://img.shields.io/badge/MCP-JSON--RPC%202.0%20(0%20Ports)-blue.svg)](#4-mcp-model-context-protocol-外部分布式扩展)

> **Super-Harnes** 是一款面向工业级真实软件工程的高性能自主代码编程智能体（Autonomous Coding Agent）。
> 核心采用 **ReAct (Reasoning + Acting)** 多步闭环决策，创新性地构建了 **200K~500K 动态弹性预算上下文滑动窗口**、**三阶段任务状态机**、**反思型死循环熔断器**、**物理快照原子回滚机制**、**MCP 零端口外部进程扩展** 与 **行业兼容级 Skills 技能扩展生态**。

---

## 🌟 核心架构与核心功能

### 1. 🧠 任务感知型 ReAct 决策中枢
- **全自主推理闭环**：严格遵循 `Thought -> Action -> Observation -> Final Answer` 逻辑流进。
- **任务阶段状态机 (`StageManager`)**：将工程任务分解为 **`EXPLORE`（探索排查态）** $\rightarrow$ **`MODIFY`（编码实施态）** $\rightarrow$ **`VERIFY`（验证闭环态）**，根据工具执行结果自动驱动阶段迁移，并动态对工具 Schema 进行置顶加权，显著增强大模型的注意力聚焦度。
- **智能死循环与停滞拦截 (`LoopDetector`)**：
  - **模式 1**：检测连续完全相同的工具调用；
  - **模式 2**：检测多工具周期性振荡循环（如 $A \rightarrow B \rightarrow A \rightarrow B$）；
  - **模式 3**：检测连续相同报错停滞。
  - **两级干预**：先出示“黄牌”注入反思警示，无效则出示“红牌”强制切断工具并执行收敛汇报（Wrap-up），彻底杜绝无限空转与 Token 浪费。

### 2. 💾 200K ~ 500K 弹性硬预算滑动窗口与分账账本
- **专款专用财务账本 (`BudgetLedger`)**：
  - **基线总预算**：默认 **200,000 Tokens**（Tier 0），动态提供高达 **176,000 Tokens** 的纯净历史滑窗运算空间；
  - **弹性扩缩容阶梯**：支持 `[200k, 250k, 350k, 500k]` 按需自动跃迁扩容；当连续两轮低于上一级 70% 水位时，自动防抖冷却缩容；
  - **隔离保护区**：系统提示词区（4k）、工具 Schema 区（6k）、工作记忆区（6k）、大输出预留区（8k），保证大模型生成超大 Diff 补丁时绝不发生截断。
- **原子轮次成对绑定 (`TurnChunk`)**：将单轮交互打成不可拆分的原子包，彻底杜绝单条消息截断导致 `tool_calls` 孤儿而触发 OpenAI API 400 校验异常。
- **三段式水位控制 (`WatermarkZone`)**：
  - 🟢 **绿区 (< 60%)**：全量直通，零信息损失；
  - 🟡 **黄区 (60% ~ 75%)**：逆向滑动窗口，从最新历史倒序装载；
  - 🔴 **红区 ($\ge$ 75%)**：主动降水位至 50%，并触发带轮次区间锚点（如 `【历史排查纪要 (#1 ~ #8)】`）与三维防抖护栏的历史增量压缩摘要。

### 3. 🛡️ 物理磁盘快照与无损回滚 (`SnapshotManager`)
- **写前快照 (Shadow Snapshot)**：任何修改代码与写入文件操作前，毫秒级备份原文件；
- **多文件事务原子性 (Patch Transaction)**：补丁修改中途只要有一处失败，自动事务级全量回滚，绝不留下半成品脏代码；
- **真实物理级 `/undo` 还原**：用户输入 `/undo` 时，不仅撤销对话历史，同时在物理硬盘上还原修改文件、删除新建文件，提供真正的“撤销后悔药”。

### 4. 🗂️ 项目级状态总线与用户全局记忆
- **项目级共享状态 (`ProjectState`)**：跨会话共享代码修改拓扑、排查行号区间及最新测试结论（`history/<project>/project_state.json`），多会话协作不撞车。
- **用户全局偏好画像 (`GlobalMemory`)**：位于 `~/.super-harnes/global_memory.json`，跨越所有工程永久沉淀个人编码偏好（如强类型标注、大纲优先）与交互风格，支持 `/remember` 与 `/forget`。
- **多会话管理与切换**：支持 `/sessions`、`/switch`、`/session new`，每个会话物理分箱，独立归档。

### 5. 🛠️ 工业级工程内置工具箱 (Builtin Tools)
- **`view_file_outline`**：基于 AST 语法树快速提取类、函数定义、参数签名及起止行号，避免为了解结构通读几千行长文件。
- **`read_file`**：自适应字符集检测（UTF-8、GBK 等），带行号范围分页阅读与字符熔断。
- **`apply_patch`**：确定性 `SEARCH/REPLACE` 代码块精准打补丁，自动剥离大模型带行号前缀的复制内容（如 `42 | `），具备修改前 AST 语法自检诊断与彩色 Unified Diff 渲染。
- **`write_file`**：安全新建文件，具备写入前快照备份与语法自检。
- **`find_by_name`**：文件名通配检索，自动集成 Git 索引加速并智能解析 `.gitignore`，剪枝跳过无关庞大目录。
- **`grep_text`**：代码级全文搜索，自动过滤二进制文件并配备输出限额转储。
- **`run_shell`**：安全终端执行器，支持双模审批（AUTO/ASK）、复合命令链切分审计（防范 `&&` 逃逸）、执行硬超时强制终止与超长日志自动落盘转储。

### 6. 🔌 MCP (Model Context Protocol) 外部进程扩展
- **标准协议支持**：基于 JSON-RPC 2.0 Stdio（标准流管道 IPC）运行，通信全在内存管道中进行，**完全不占用任何本地网络端口（0 端口占用）**。
- **内核级生命周期托管**：Windows 下采用内核级 Job Object 托管进程树，注册退出钩子，进程异常退出或 Ctrl+C 时连带释放外部子进程，绝不残留僵尸后台。
- **命名空间与输出限额**：采用 `mcp__{server}__{tool}` 隔离前缀消除工具命名冲突，配置级单项输出限额拦截。

### 7. 🧩 原生 Skills 技能生态体系
- 遵循行业主流 `SKILL.md` 规范（兼容 OpenAI / Claude Code / skills.sh 技能生态）。
- 具备多级发现体系（工作区 `.skills/` $\rightarrow$ 全局 `~/.super-harnes/skills` $\rightarrow$ Codex 兼容目录）。
- 默认预置 4 套高阶专业工程技能：
  - **`codebase-design`**：复杂架构设计、DESIGN-IT-TWICE 方案推演；
  - **`codebase-onboarding`**：全新陌生长代码库极速上手与导读；
  - **`diagnosing-bugs`**：棘手缺陷定位、根因追踪与闭环验证；
  - **`domain-modeling`**：业务领域建模与架构决策记录 (ADR)。

### 8. 💻 现代化终端 TUI 交互体验
- 基于 `prompt_toolkit` 与 `rich` 打造，支持鼠标交互、流式打字机思考展示、实时 Token 水位进度条、彩色 Diff 审核、命令补全与全套斜杠快捷指令。

---

## 🏗️ 架构流转时序

```text
               ┌───────────────────────────────┐
               │    用户输入 (User Prompt)      │
               └──────────────┬────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │ 1. 上下文组装与弹性滑窗 (ContextManager)      │
        │    - 注入全局用户画像与偏好 (GlobalMemory)   │
        │    - 注入不可变 System Prompt (Prompt Cache) │
        │    - 注入永久锁定工作记忆 (WorkingMemory)    │
        │    - 弹性滑窗动态评估 (200k ~ 500k Tiers)    │
        │    - 任务阶段状态机导向加权 (StageManager)   │
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
│ 3. 循环停滞检测 (LoopDetector)│        │ 6. 生成最终结论 (Final Answer)│
│  - 判定重复调用与振荡死循环   │        │  - 更新 WorkingMemory 达成态  │
│  - 必要时黄牌警告或红牌收尾   │        │  - 增量落盘至 history/*.jsonl │
└──────────────┬────────────────┘        │  - 终端流式排版呈现给用户     │
               │                         └───────────────────────────────┘
               ▼
┌───────────────────────────────┐
│ 4. ToolExecutor 统一调度分发  │
│  - 修改代码: 写前快照+原子事务│
│  - Shell命令: 审批策略校验    │
│  - MCP服务: 零端口管道RPC调用 │
└──────────────┬────────────────┘
               │
               ▼
┌───────────────────────────────┐
│ 5. 观察回填与状态推进         │
│  - 更新项目状态总线(修改/测试)│
│  - StageManager 推进阶段迁移  │
│  - 回到步骤 2 进行下一步思考  │
└───────────────────────────────┘
```

---

## 📁 目录结构与功能映射

```text
super-harnes/
│
├── core/                        # 【认知与决策中枢】
│   ├── agent.py                 # ReActAgent: 纯净的多步推理循环引擎
│   ├── stage_manager.py         # 任务阶段状态机 (EXPLORE -> MODIFY -> VERIFY)
│   ├── loop_detector.py         # 死循环与停滞智能检测熔断器
│   ├── session.py               # 多会话元数据管理核心
│   └── prompt.py                # 系统提示词规范与核心准则
│
├── cli/                         # 【终端交互与呈现】
│   ├── console.py               # 交互控制台主循环
│   ├── commands.py              # 全套斜杠命令处理器 (/status, /switch, /undo 等)
│   └── ui.py                    # 基于 Rich 与 Prompt_Toolkit 的现代 TUI
│
├── context/                     # 【上下文与记忆中枢】
│   ├── budget.py                # 200k ~ 500k 动态弹性预算账本 (BudgetLedger)
│   ├── manager.py               # 会话上下文总管，三段式水位调度
│   ├── window.py                # 逆向滑动窗口与原子轮次 (TurnChunk)
│   ├── project_state.py         # 项目级跨会话共享工作区状态总线
│   ├── global_memory.py         # 用户全局跨工程偏好画像 (~/.super-harnes)
│   ├── snapshot.py              # 物理磁盘快照与原子回滚事务
│   ├── summarizer.py            # 区间追踪与三维防抖长期记忆摘要器
│   └── token_counter.py         # 高精度 Token 计算器
│
├── tools/                       # 【工具体系与安全沙箱】
│   ├── framework/               # -- 底座支撑
│   │   ├── registry.py          # 工具注册中心与 Schema 自动生成
│   │   ├── executor.py          # 工具调度执行器与错误隔离
│   │   ├── policies.py          # 命令审批策略 (AUTO / ASK 双模) 与链式切分
│   │   ├── workspace.py         # 工作区隔离沙箱与原子写
│   │   └── output_clamp.py      # 超长输出熔断截断与日志转储
│   └── builtin/                 # -- 原生内置安全工具
│       ├── file_tools.py        # read_file, list_files, view_file_outline, write_file
│       ├── search_tools.py      # find_by_name, grep_text (毫秒级代码检索)
│       ├── patch_tool.py        # apply_patch (确定性 SEARCH/REPLACE 原子补丁)
│       ├── shell_tool.py        # run_shell (终端受控执行)
│       └── skill_tools.py       # load_skill, list_available_skills
│
├── mcp/                         # 【MCP 外部进程扩展】
│   ├── client.py                # 标准 JSON-RPC 2.0 Stdio 通信客户端 (JobObject 托管)
│   ├── manager.py               # 批量配置加载与子进程生命周期管理
│   ├── bridge.py                # 动态命名空间隔离桥接器
│   ├── config.py                # 信任等级与配置模型
│   └── servers/                 # 自带独立示例服务 (calc_server, sysinfo_server)
│
├── skills/                      # 【技能生态管理】
│   ├── manager.py               # 多级技能发现与检索加载
│   ├── skill.py                 # SKILL.md Frontmatter 解析与渐进式展示
│   └── installer.py             # 外部技能一键安装器
│
├── .skills/                     # 【工程内置专家技能包】
│   ├── codebase-design/         # 复杂系统设计与方案权衡技能
│   ├── codebase-onboarding/     # 陌生长工程快速摸底导读技能
│   ├── diagnosing-bugs/         # 深度缺陷诊断与根因定位技能
│   └── domain-modeling/         # 业务领域建模与架构决策技能
│
├── config/                      # 【集中化配置】
│   ├── settings.py              # 统一路径、默认模型与审批模式读取
│   └── mcp_servers.json         # 外部 MCP 独立服务连接清单
│
├── scripts/                     # 【运维与启动脚本】
│   ├── super.cmd / super.ps1    # 免激活一键启动终端
│   └── run_checks.py            # 全量 145 项回归测试运行器
│
├── tests/                       # 【工业级单元与集成测试】(145 项测试用例全部覆盖)
├── .github/workflows/ci.yml     # GitHub Actions 自动化测试流水线
├── .env.example                 # 环境变量模板
├── .gitignore                   # 严谨的 Git 忽略名单
├── requirements.txt             # 生产依赖声明
├── LICENSE                      # MIT 开源许可证
└── main.py                      # 【系统统一启动入口】
```

---

## 🚀 快速上手

### 1. 环境准备与依赖安装
确保安装了 Python 3.10 及以上环境：
```bash
git clone https://github.com/your-username/super-harnes.git
cd super-harnes

# 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装生产依赖
pip install -r requirements.txt
```

### 2. 配置大模型 API 密钥
复制环境变量模板：
```bash
cp .env.example .env  # Windows: copy .env.example .env
```
编辑 `.env` 文件（开箱即用支持 DeepSeek，同时兼容 OpenAI、通义千问、Kimi、智谱 GLM 等任意标准接口）：
```ini
LLM_API_KEY=your_actual_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat

# 命令执行审批模式: auto (Claude 风格全自动免确认，推荐) / ask (敏感命令逐条人工审批)
APPROVAL_MODE=auto

# 上下文基线总预算 (默认 200000，按需可调)
AGENT_TOTAL_BUDGET=200000
```

### 3. 执行自动化回归测试
在正式启动前，一键验证全量 145 个自动化测试用例：
```bash
python scripts/run_checks.py
```

### 4. 启动交互式 Agent
```bash
python main.py
```
*(Windows 用户也可直接双击运行 `.\scripts\super.cmd` 或在 PowerShell 中执行 `.\scripts\super.ps1`)*

---

## 🕹️ 常用控制台指令指南

在交互控制台中输入 `/` 可随时触发指令补全，核心指令如下：

| 指令 | 说明 |
| :--- | :--- |
| **`/status`**, **`/memory`** | 实时查看当前工作区感知状态、已读/已改文件、MCP 挂载服务与当前 Token 预算阶梯 |
| **`/auto`** | 一键切换至类似 Claude Code 的 **AUTO 全自动模式**（安全命令全自动免审批，高危命令阻断） |
| **`/ask`** | 一键切换至 **ASK 人工审批模式**（所有修改与执行命令均弹窗提示 `[y/n/a]`） |
| **`/undo`** | **物理级无损撤销**：不仅回退上一轮会话历史，同时还原磁盘被改动的文件 |
| **`/skills`** | 列出当前已挂载的所有专家技能包（包括内置技能与自定义技能） |
| **`/skill load <name>`** | 手动查阅并激活指定技能的 SOP 执行规约 |
| **`/skill install <repo>`**| 从 GitHub 仓库或本地路径一键安装新的专家技能 |
| **`/sessions`** | 列出所有会话归档列表，查看当前会话状态与 Token 占用 |
| **`/switch <name>`** | 动态切换到指定会话，自动无缝恢复其全部历史与工作状态 |
| **`/session new <name>`** | 创建并激活一个全新的平行会话 |
| **`/remember <偏好>`** | 永久记录一条个人编码偏好或习惯，跨项目永久生效 |
| **`/profile`** | 查看保存在用户主目录的全局画像与已登记项目索引 |
| **`/restore`** | 从磁盘 `history/` 恢复当前会话的中断历史 |
| **`/reset`**, **`/new`** | 清空内存对话历史，开启全新排查任务 |
| **`/help`** | 显示完整的控制台交互帮助卡片 |
| **`quit`**, **`exit`** | 优雅退出，自动安全释放所有外部 MCP 进程与句柄 |

---

## 🤝 参与贡献
我们非常欢迎社区开发者的 Issue 与 Pull Request！
在提交 PR 之前，请确保运行 `python scripts/run_checks.py` 并且全量 145 项测试均能通过。

---

## 📄 开源许可证
本项目基于 [MIT License](LICENSE) 开源，商业友好，可自由二次开发与集成。
