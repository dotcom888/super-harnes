# Super-Harnes 智能体自动化与全场景测试用例规范全景手册

> **文档版本**: v2.5.0  
> **文档密级**: 核心工程技术资产 / 公开开源技术规范  
> **发布日期**: 2026-09-28  
> **面向对象**: Agent 核心研发架构师、QA 自动化测试工程师、评测算法工程师与开源贡献者  
> **被测系统**: **Super-Harnes** 工业级自主代码编程智能体 (Autonomous Coding Agent)  
> **测试通过基线**: 全量 145 项核心自动化单元与集成回归测试通过 (100% Pass Rate)

---

## 目录
1. [测试架构与测试全景 (Test Strategy & Architecture)](#1-测试架构与测试全景)
   - 1.1 测试设计原则与分层模型
   - 1.2 被测系统架构分解与模块覆盖矩阵
   - 1.3 测试执行环境与依赖规范
2. [核心决策与状态机测试套件 (Core ReAct & State Machine)](#2-核心决策与状态机测试套件)
   - 2.1 ReAct 智能体循环与决策测试 (TC-CORE)
   - 2.2 死循环与停滞拦截测试 (TC-LOOP)
   - 2.3 任务阶段状态机与动态重排/掩码测试 (TC-STAGE)
   - 2.4 Prompt 构建与 KV Cache 前缀稳态测试 (TC-PROMPT)
3. [200K~500K 弹性硬预算与上下文治理测试套件 (Context & Budget Ledger)](#3-200k500k-弹性硬预算与上下文治理测试套件)
   - 3.1 弹性预算账本与阶梯扩缩容测试 (TC-BUDGET)
   - 3.2 三段式水位控制与倒序滑窗测试 (TC-WINDOW)
   - 3.3 原子轮次绑定与 Tool Calls 成对清洗测试 (TC-CHUNK)
   - 3.4 增量历史纪要与三维防抖测试 (TC-SUMM)
   - 3.5 工作记忆 (Working Memory) 与文件区间合并测试 (TC-WM)
   - 3.6 物理快照与原子回滚事务测试 (TC-SNAP)
   - 3.7 项目级状态总线与全局用户画像测试 (TC-STATE)
4. [工业级工具框架与内置工具箱测试套件 (Tools Framework & Builtin Tools)](#4-工业级工具框架与内置工具箱测试套件)
   - 4.1 增强补丁工具 (apply_patch) 与容错自检测试 (TC-PATCH)
   - 4.2 本地文件读写与大纲视图测试 (TC-FILE)
   - 4.3 终端命令策略与人机审批测试 (TC-SHELL)
   - 4.4 代码检索与聚类工具测试 (TC-SEARCH)
   - 4.5 语义输出压缩与磁盘溢出落盘测试 (TC-CLAMP)
5. [MCP 外部扩展与 Skills 生态测试套件 (MCP & Skills Subsystem)](#5-mcp-外部扩展与-skills-生态测试套件)
   - 5.1 MCP 进程管理、JSON-RPC 2.0 与级联发现测试 (TC-MCP)
   - 5.2 MCP 协议健壮性、管道防死锁与子进程清理测试 (TC-MCP-PROT)
   - 5.3 Skills 发现、Frontmatter 解析与渐进式展示测试 (TC-SKILL)
6. [CLI 控制台、会话生命周期与人机协同测试套件 (CLI & Session Lifecycle)](#6-cli-控制台会话生命周期与人机协同测试套件)
   - 6.1 多会话隔离、新建、切换与磁盘持久化测试 (TC-SESS)
   - 6.2 斜杠指令集处理与工作区切换测试 (TC-CMD)
   - 6.3 Rich 终端渲染、差异高亮与审批交互测试 (TC-UI)
7. [高级非功能性与鲁棒性防御测试套件 (Advanced Robustness & Security)](#7-高级非功能性与鲁棒性防御测试套件)
   - 7.1 安全沙箱穿透与逃逸拦截测试 (TC-SEC)
   - 7.2 极端边界与容灾压测 (TC-STRESS)
   - 7.3 异常中断与进程恢复测试 (TC-RECOVER)
8. [端到端与真实软件工程场景回归测试套件 (E2E & SWE Scenarios)](#8-端到端与真实软件工程场景回归测试套件)
   - 8.1 典型 SWE 单文件缺陷修复闭环 (TC-E2E-01)
   - 8.2 多文件架构重构与测试回归 (TC-E2E-02)
   - 8.3 外部 MCP 工具协同复杂计算与系统自检 (TC-E2E-03)
9. [自动化测试执行指南与 CI/CD 质量门禁 (Execution & CI/CD)](#9-自动化测试执行指南与-cicd-质量门禁)
   - 9.1 全量测试运行与参数规范
   - 9.2 145 项回归测试映射字典
   - 9.3 GitHub Actions 流水线自动化门禁

---

## 1. 测试架构与测试全景

### 1.1 测试设计原则与分层模型
针对自主代码编程智能体（Coding Agent）的高复杂度与非确定性决策流，Super-Harnes 建立了**纵深防御测试模型（Defense-in-Depth Testing Matrix）**，将测试体系划分为四个确定性梯队：

```
  +--------------------------------------------------------------+
  | Level 4: SWE 真实工程端到端场景 (E2E & SWE-bench)            |
  | 模拟复杂缺陷排查定位、多文件修改、闭环验证与最终报告交付     |
  +--------------------------------------------------------------+
  | Level 3: 安全穿透与极限鲁棒性测试 (Security & Stress)        |
  | 命令注入防范、路径穿越拦截、500k 上下文防爆与极端容灾恢复   |
  +--------------------------------------------------------------+
  | Level 2: 子系统联动集成测试 (Subsystem Integration)          |
  | ReAct 决策 + 滑窗治理 + MCP 外部扩展 + 物理磁盘快照事务回滚 |
  +--------------------------------------------------------------+
  | Level 1: 确定性单元与状态机单测 (Unit & Regression Tests)    |
  | 145 项核心回归单元单测全量通过 (100% 确定性断言覆盖)         |
  +--------------------------------------------------------------+
```

#### 四大核心测试原则：
1. **确定性优先原则 (Determinism First)**：底层状态机、分账账本、Token 统计、安全策略与补丁 AST 解析必须通过零随机性的自动化单元测试严格锁定。
2. **沙箱与物理隔离原则 (Sandbox & Workspace Isolation)**：所有涉及文件写入、磁盘快照还原、Shell 命令执行的测试，必须动态重定向至临时隔离目录（`tempfile.TemporaryDirectory`），严禁污染研发机真实环境。
3. **零孤儿进程原则 (Zero-Orphan Process Guarantee)**：所有 MCP 外部子进程生命周期测试必须严格验证异常中断与退出时子进程树（PID Tree）的彻底回收。
4. **真实回归对齐原则 (Ground-Truth Alignment)**：测试断言直接基于真实生产中的边界 Bug（如行号前缀、孤儿 tool_calls、Windows CRLF 换行、Stderr 管道阻塞等）构建。

### 1.2 被测系统架构分解与模块覆盖矩阵

| 被测模块代号 | 核心源码组件 | 核心功能与关键路径 | 对应自动化测试文件 | 测试用例数 |
| :--- | :--- | :--- | :--- | :---: |
| **MOD-CORE** | `core/agent.py`<br>`core/loop_detector.py`<br>`core/stage_manager.py`<br>`core/prompt.py` | ReAct 闭环循环、死循环模式识别、三阶段状态流转、KV Cache 稳态 | `tests/test_loop_detector.py`<br>`tests/test_output_optimization_and_tool_precision.py` | 18 |
| **MOD-CTX** | `context/budget.py`<br>`context/manager.py`<br>`context/window.py`<br>`context/summarizer.py`<br>`context/snapshot.py` | 200k~500k 弹性预算分账、绿黄红三段水位、原子轮次清洗、物理快照回滚 | `tests/test_context.py`<br>`tests/test_session.py` | 55 |
| **MOD-STATE** | `context/project_state.py`<br>`context/global_memory.py` | 跨会话共享修改拓扑、持久化全局用户偏好与开发习惯 | `tests/test_session.py` | 8 |
| **MOD-TOOL** | `tools/builtin/patch_tool.py`<br>`tools/builtin/file_tools.py`<br>`tools/builtin/shell_tool.py`<br>`tools/builtin/search_tools.py`<br>`tools/framework/*` | 补丁事务原子性、AST 语法预检、行号剥离、命令策略分级、输出语义截断与落盘透镜 | `tests/test_local_terminal_tools.py`<br>`tests/test_output_optimization_and_tool_precision.py` | 32 |
| **MOD-MCP** | `mcp/client.py`<br>`mcp/bridge.py`<br>`mcp/manager.py`<br>`mcp/config.py` | JSON-RPC 2.0 stdio 通信、级联配置扫描与项目级覆盖、管道防死锁、子进程回收 | `tests/test_mcp.py` | 10 |
| **MOD-SKILL** | `skills/skill.py`<br>`skills/manager.py`<br>`skills/installer.py` | 专家技能扫描挂载、YAML Frontmatter 解析、渐进式披露、Git/本地安装 | `tests/test_skills.py` | 4 |
| **MOD-CLI** | `cli/commands.py`<br>`cli/console.py`<br>`cli/ui.py`<br>`core/session.py` | 终端人机协同、斜杠指令分发、Rich 彩色卡片、审批交互、物理多会话分箱 | `tests/test_cli_ui.py`<br>`tests/test_session.py` | 18 |
| **合计** | **全部 7 大子系统** | **工业级 Autonomous Coding Agent 全链路核心** | **8 个测试套件文件** | **145 项基线** |

### 1.3 测试执行环境与依赖规范
- **Python 运行时**: Python 3.10, 3.11, 3.12, 3.13 (跨平台 Windows 10/11, Ubuntu 22.04 LTS, macOS 14+)。
- **外部依赖库**:
  - `openai >= 1.0.0` (标准大模型协议 client 与 types)
  - `tiktoken >= 0.7.0` (高精度 Token 计数与分词账本)
  - `rich >= 13.0.0` (终端美化与彩色 Diff 渲染)
  - `python-dotenv >= 1.0.0` (环境变量动态加载)
  - `psutil >= 5.9.0` (系统资源与进程树监控)
- **测试框架**: Python 内置 `unittest` 框架，开箱即用，零额外第三方测试框架依赖。

---

## 2. 核心决策与状态机测试套件 (Core ReAct & State Machine)

### 2.1 ReAct 智能体循环与决策测试 (TC-CORE)

#### 用例 TC-CORE-001: 纯文本解答时的自然终止 (Natural Exit)
- **测试标识**: `TC-CORE-001`
- **被测方法**: `core.agent.ReActAgent.run`
- **测试目的**: 验证当模型认为无需调用工具即可完成解答时，循环能够自然退出，不产生多余空转步数。
- **前置条件**: 初始化 `ReActAgent`，Mock OpenAI Client 返回纯文本消息（`content="Python 中 GIL 保证了单个线程独占字节码执行权"`, `tool_calls=None`）。
- **操作步骤**: 调用 `agent.run(user_prompt="解释 GIL")`。
- **预期结果**:
  1. 循环在第 1 步自然终止；
  2. 返回正确的文本解答；
  3. `context_manager.turn_count` 递增 1；
  4. 最终状态未触发熔断或异常标记。
- **对应自动化测试**: `tests/test_loop_detector.py::TestUnboundedReActExecution.test_unbounded_mode_natural_exit_when_no_tool_calls`

#### 用例 TC-CORE-002: 到达固定步数上限时的强制收尾 (Graceful Wrap-up on Max Steps)
- **测试标识**: `TC-CORE-002`
- **被测方法**: `core.agent.ReActAgent.run`
- **测试目的**: 验证设置 `max_steps` 上限后，最终步能够自动切断工具暴露，强制模型输出综合答复。
- **前置条件**: 设定 `max_steps=5`。Mock 模型前 4 步持续请求 `read_file`。
- **操作步骤**: 执行循环直到第 5 步。
- **预期结果**:
  1. 在第 5 步向模型发送请求时，`tools` 参数被强制置为 `None`；
  2. 提示词末尾单调注入关键横幅：`[重要提醒: 本轮已达最终步，工具调用已关闭...]`；
  3. 模型返回事实汇总文本，循环安全退出，绝不因超步发生死循环。
- **对应自动化测试**: `tests/test_context.py::TestContextEnhancements.test_point_22_step_awareness_and_graceful_wrapup`

#### 用例 TC-CORE-003: 轮内动态 Token 预算超限熔断 (Dynamic In-turn Circuit Breaker)
- **测试标识**: `TC-CORE-003`
- **被测方法**: `core.agent.ReActAgent.run`
- **测试目的**: 验证轮内单步工具返回内容暴涨导致上下文超过允许安全上限时，触发动态熔断，阻断 400 Context Length Exceeded。
- **前置条件**: 构造单步工具调用返回超过 50,000 字符的大量代码，使上下文瞬时超出 `total_budget - output_reserve`。
- **操作步骤**: 驱动 Agent 进入下一步推理。
- **预期结果**:
  1. 触发轮内熔断逻辑，终止后续工具派发；
  2. 生成带有 `【系统保护】轮内多步推理消耗已达上下文上限...已安全熔断` 的保护性消息；
  3. 当前轮次安全结束（`finish_current_turn`），未向底层 API 发送超限请求。
- **对应自动化测试**: `tests/test_context.py::TestContextEnhancements.test_point_13_react_inturn_dynamic_circuit_breaker`

#### 用例 TC-CORE-004: 轮内早期陈旧观察结果折叠裁剪 (In-turn Observation Pruning)
- **测试标识**: `TC-CORE-004`
- **被测方法**: `core.agent.ReActAgent._prune_inturn_observations`
- **测试目的**: 验证多步排查累积时，自动折叠 2 步以前且长度 >600 字符的冗长工具返回，释放上下文。
- **前置条件**: 构造包含 4 步 `tool` 结果的 messages 序列，前 2 步 tool content 超过 1000 字符。
- **操作步骤**: 调用 `_prune_inturn_observations`。
- **预期结果**:
  1. 返回剪枝数量 `pruned_count == 2`；
  2. 前两步消息正文折叠为 `前200字符 ...[历史观察结果已由 Agent 消化...]... 后100字符`；
  3. 最近 2 步观察结果完整保留，未发生篡改。
- **对应自动化测试**: `tests/test_context.py::TestContextEnhancements.test_point_25_inturn_observation_pruning`

---

### 2.2 死循环与停滞拦截测试 (TC-LOOP)

#### 用例 TC-LOOP-001: 模式 1 - 连续完全相同工具调用黄牌与红牌熔断
- **测试标识**: `TC-LOOP-001`
- **被测类**: `core.loop_detector.LoopDetector`
- **测试目的**: 验证相同工具及参数连续调用 >=3 次出黄牌、>=4 次出红牌切断。
- **输入序列**: 连续输入 4 次 `read_file(path='app.py', start_line=1)`。
- **预期结果**:
  - 第 1 次: `LoopState.NORMAL`；
  - 第 2 次: `LoopState.NORMAL`；
  - 第 3 次: `LoopState.WARNING`（黄牌），诊断原因为连续相同调用；
  - 第 4 次: `LoopState.FORCE_WRAPUP`（红牌），强制要求关闭工具。
- **对应自动化测试**: `tests/test_loop_detector.py::TestLoopDetector.test_mode_1_consecutive_duplicate_calls`

#### 用例 TC-LOOP-002: 模式 2 - 多工具周期性震荡循环识别 (Oscillating Cycles)
- **测试标识**: `TC-LOOP-002`
- **被测类**: `core.loop_detector.LoopDetector`
- **测试目的**: 验证周期长度为 2（如 A->B->A->B->A->B）的多工具震荡死循环识别能力。
- **输入序列**: 交替记录 `grep_text` 与 `find_by_name`，重复 3 个周期。
- **预期结果**:
  1. 周期达到 3 次时，识别为震荡死循环；
  2. 状态跃迁至 `LoopState.WARNING` / `LoopState.FORCE_WRAPUP`；
  3. 诊断信息明确指明震荡工具指纹。
- **对应自动化测试**: `tests/test_loop_detector.py::TestLoopDetector.test_mode_2_oscillating_ping_pong_cycles`

#### 用例 TC-LOOP-003: 模式 3 - 连续相同报错硬撞熔断
- **测试标识**: `TC-LOOP-003`
- **被测类**: `core.loop_detector.LoopDetector`
- **测试目的**: 验证针对工具连续返回相同错误（如权限不足、SEARCH块不匹配）的停滞防御。
- **输入序列**: 连续 3 次返回 `【补丁失败】：未找到匹配的 SEARCH 块`。
- **预期结果**:
  1. 检测到重复错误特征；
  2. 触发黄牌警告，阻断盲目重复打补丁。
- **对应自动化测试**: `tests/test_loop_detector.py::TestLoopDetector.test_mode_3_consecutive_identical_errors`

#### 用例 TC-LOOP-004: 自主排查遇死循环强制脱困 (Unbounded Loop Recovery)
- **测试标识**: `TC-LOOP-004`
- **被测类**: `core.agent.ReActAgent`
- **测试目的**: 验证在无步数上限模式下，陷入死循环后 Agent 能够被红牌强制截断并完成总结答复。
- **预期结果**: 捕获死循环红牌，在下一步置空 tools 强制收敛，返回优雅退出说明。
- **对应自动化测试**: `tests/test_loop_detector.py::TestUnboundedReActExecution.test_unbounded_mode_force_wrapup_on_dead_loop`

---

### 2.3 任务阶段状态机与动态重排测试 (TC-STAGE)

#### 用例 TC-STAGE-001: 工具反馈驱动状态机自主流转
- **测试标识**: `TC-STAGE-001`
- **被测类**: `core.stage_manager.StageManager`
- **测试目的**: 验证 EXPLORE -> MODIFY -> VERIFY 及其异常回退的自主状态跃迁。
- **执行步骤与断言**:
  1. 初始状态为 `TaskStage.EXPLORE`；
  2. 传入 `view_file_outline` 成功返回 -> 保持 `EXPLORE`；
  3. 传入 `apply_patch` 并返回 `【补丁成功】` -> 自动迁移至 `TaskStage.VERIFY`；
  4. 传入 `run_shell(pytest)` 并返回 `FAILED: 1 error` -> 自动回退至 `TaskStage.EXPLORE` 进行复查；
  5. 再次 `apply_patch` 成功并执行 `run_shell` 返回 `passed` -> 确立在 `TaskStage.VERIFY`。
- **对应自动化测试**: `tests/test_output_optimization_and_tool_precision.py::TestSpoolingAndOutputOptimization.test_stage_manager_lifecycle_and_reordering`

#### 用例 TC-STAGE-002: 动态工具优先级重排 (Dynamic Priority Reordering)
- **测试标识**: `TC-STAGE-002`
- **被测方法**: `core.stage_manager.StageManager.reorder_or_mask_schemas`
- **测试目的**: 验证不同阶段下向大模型呈现的工具 Schema 自动重排置顶。
- **预期结果**:
  - `EXPLORE` 阶段：`view_file_outline`、`grep_text`、`read_file` 排序位于最前；
  - `MODIFY` 阶段：`apply_patch`、`write_file` 排序位于最前；
  - `VERIFY` 阶段：`run_shell` 排序位于最前；
  - 置顶工具显著强化大模型注意力对焦。
- **对应自动化测试**: `tests/test_output_optimization_and_tool_precision.py::TestSpoolingAndOutputOptimization.test_stage_manager_lifecycle_and_reordering`

---

### 2.4 Prompt 构建与 KV Cache 前缀稳态测试 (TC-PROMPT)

#### 用例 TC-PROMPT-001: System Prompt 绝对不可变性
- **测试标识**: `TC-PROMPT-001`
- **测试目的**: 验证多轮对话中 System 角色消息内容 100% 不变，杜绝动态内容插入导致 Prompt Cache 失效。
- **预期结果**:
  - 无论轮次如何推进，生成的 `system` 消息与初始 `system` 消息哈希完全一致；
  - 动态记忆全部迁移至 User 角色注记或 Tool 结果中注入。
- **对应自动化测试**: `tests/test_context.py::TestContextEnhancements.test_point_1_system_prompt_immutability`

#### 用例 TC-PROMPT-002: 轮内严格单调追加 (Strict Append-Only In-turn Messages)
- **测试标识**: `TC-PROMPT-002`
- **测试目的**: 验证 ReAct 循环中的 step banner 仅单调附加在最新 Tool Result 尾部。
- **预期结果**:
  - 检查第 1 步到第 N 步发送的 messages 列表；
  - 早期已经发送过的 user、assistant、tool 消息未被修改或替换；
  - 保证大模型 API 服务端的 KV Cache 保持稳态命中。
- **对应自动化测试**: `tests/test_session.py::TestMultiSessionManagement.test_react_inturn_prompt_cache_strict_append_only`

---

## 3. 200K~500K 弹性硬预算与上下文治理测试套件 (Context & Budget Ledger)

### 3.1 弹性预算账本测试 (TC-BUDGET)

#### 用例 TC-BUDGET-001: 200k 默认基线与分账明细守恒
- **测试标识**: `TC-BUDGET-001`
- **被测类**: `context.budget.BudgetLedger`
- **测试目的**: 验证默认总预算 200,000 Tokens 下各专款专用预留区划分正确。
- **断言标准**:
  - `total_budget == 200000`；
  - `system_reserve == 4000`；
  - `tools_reserve == 6000`；
  - `memory_reserve == 6000`；
  - `output_reserve == 8000`；
  - `history_budget == 176000`；
  - 预留和严格等于 `total_budget - history_budget`。
- **对应自动化测试**: `tests/test_context.py::TestContextEnhancements.test_point_2_budget_ledger_allocation`

#### 用例 TC-BUDGET-002: 弹性阶梯按需自动跃迁扩容
- **测试标识**: `TC-BUDGET-002`
- **测试目的**: 验证消耗触达 85% 上限时，预算梯队按 `[200k, 250k, 350k, 500k]` 自动向上扩容。
- **执行步骤与断言**:
  - 当需要 180,000 Tokens 时触发 `expand_if_needed`；
  - `total_budget` 自动跃迁至 `250,000`；
  - 进一步需要 260,000 Tokens 时，再次跃迁至 `350,000`；
  - 最大可扩容至 `500,000` Tokens。
- **对应自动化测试**: `tests/test_context.py::TestContextEnhancements.test_point_23_dynamic_budget_ledger_200k_default_and_elastic_expansion`

#### 用例 TC-BUDGET-003: 低水位防抖冷却缩容
- **测试标识**: `TC-BUDGET-003`
- **测试目的**: 验证当任务进入轻量交互且连续两轮低于上一级 70% 水位时，触发安全缩容。
- **断言标准**:
  - 第 1 轮低水位：保持高预算，记录冷却计数 1；
  - 第 2 轮低水位：平滑缩容降级，防止阶梯频繁跳动。
- **对应自动化测试**: `tests/test_context.py::TestContextEnhancements.test_point_4_anti_jitter_debounce`

#### 用例 TC-BUDGET-004: 账本参数动态重算与非法参数拦截
- **测试标识**: `TC-BUDGET-004`
- **测试目的**: 验证非负数校验以及预留之和超出总预算时的异常防护。
- **断言标准**:
  - 传入负数或布尔值抛出 `ValueError`；
  - 预留总和 >= 总预算时抛出 `ValueError`。
- **对应自动化测试**: `tests/test_context.py::TestContextEnhancements.test_point_5_budget_ledger_validation_and_dynamic_recalc`

---

### 3.2 三段式水位控制与倒序滑窗测试 (TC-WINDOW)

#### 用例 TC-WINDOW-001: 绿区 (<60%) 全量直通
- **测试标识**: `TC-WINDOW-001`
- **测试目的**: 验证占用在 60% 以下时无任何历史损失。
- **预期结果**: 水位返回 `GREEN`，所有历史轮次 100% 原样保留。
- **对应自动化测试**: `tests/test_context.py::TestContextEnhancements.test_point_9_green_zone_no_duplicate_injection`

#### 用例 TC-WINDOW-002: 黄区 (60%~75%) 倒序滑窗与严格无穿孔
- **测试标识**: `TC-WINDOW-002`
- **测试目的**: 验证黄区下从最新历史倒序装配，且淘汰早期轮次时保证保留的历史区间严格连续。
- **预期结果**:
  - 水位返回 `YELLOW`；
  - 保留的历史轮次索引为连续递增序列（如 `[5, 6, 7, 8]`），绝对无穿孔丢步（如 `[2, 4, 7]` 绝不发生）。
- **对应自动化测试**: `tests/test_session.py::TestSafeSlidingWindowAndSession.test_sliding_window_strict_continuity_no_perforation`

#### 用例 TC-WINDOW-003: 红区 (>=75%) 增量纪要压缩与水位恢复
- **测试标识**: `TC-WINDOW-003`
- **测试目的**: 验证红区下主动生成带区间标记的历史纪要，并成功将水位释放回 50% 以下。
- **预期结果**:
  - 生成 `【历史排查纪要 (#1 ~ #N)】`；
  - 后续新轮次在轻量交互中平滑从 RED 恢复至 GREEN。
- **对应自动化测试**: `tests/test_context.py::TestContextEnhancements.test_point_7_watermark_dynamic_recovery_from_red_zone`

#### 用例 TC-WINDOW-004: 最终硬门禁防线保全 (Hard Gatekeeper)
- **测试标识**: `TC-WINDOW-004`
- **测试目的**: 验证无论历史如何堆叠，硬门禁确保总 Tokens 绝对不侵占 `output_reserve`（8000 Tokens）。
- **预期结果**:
  - 当总计算量超出安全红线时，截断多余 WorkingMemory；
  - 输出日志：`触发硬门禁截断: 实际 Tokens 超过允许上限...`。
- **对应自动化测试**: `tests/test_session.py::TestSafeSlidingWindowAndSession.test_hard_gatekeeper_enforces_output_reserve`

---

### 3.3 原子轮次绑定与成对清洗测试 (TC-CHUNK)

#### 用例 TC-CHUNK-001: 孤儿 Tool 与孤儿 Tool Calls 双向成对清洗
- **测试标识**: `TC-CHUNK-001`
- **测试目的**: 彻底杜绝 API 400 校验异常（Missing tool_calls response 或 orphaned tool message）。
- **前置条件**: 构造包含未闭合 tool_calls 与孤立 tool 的历史数据。
- **预期结果**: `TurnChunk` 自动识别并双向剥离非成对消息，保留完全闭合的原子包。
- **对应自动化测试**: `tests/test_session.py::TestSafeSlidingWindowAndSession.test_turn_chunk_atomic_pairing_and_sanitization`

#### 用例 TC-CHUNK-002: 异常崩溃恢复时隔离未完结轮次
- **测试标识**: `TC-CHUNK-002`
- **测试目的**: 验证断电或崩溃重启恢复时，磁盘上未完成的半成品轮次不被加载进 active chunks。
- **预期结果**: `restore_from_disk` 仅装载带有完成标记的 turns，悬挂脏数据被安全隔离。
- **对应自动化测试**: `tests/test_session.py::TestSafeSlidingWindowAndSession.test_disk_restore_isolates_uncompleted_turns`

---

### 3.4 增量历史纪要与三维防抖测试 (TC-SUMM)

#### 用例 TC-SUMM-001: 增量摘要轮次区间精准锚定
- **测试标识**: `TC-SUMM-001`
- **测试目的**: 验证生成的长文本纪要包含明确的轮次锚点（如 `【历史排查纪要 (#1 ~ #8)】`）。
- **断言标准**: 正则匹配出起止轮次 ID，杜绝无边界抽象摘要导致的上下文混淆。
- **对应自动化测试**: `tests/test_context.py::TestContextEnhancements.test_point_3_summary_range_tracking`

#### 用例 TC-SUMM-002: 会话长期摘要严格物理隔离
- **测试标识**: `TC-SUMM-002`
- **测试目的**: 验证多会话之间长期摘要相互独立，切换会话时绝不串话。
- **预期结果**: 会话 A 生成的纪要仅存在于 A 的上下文，会话 B 拥有完全独立的纪要栈。
- **对应自动化测试**: `tests/test_session.py::TestProjectLevelStateAndFusionWorkingMemory.test_long_term_summary_strict_isolation_between_sessions`

---

### 3.5 工作记忆与文件区间合并测试 (TC-WM)

#### 用例 TC-WM-001: 排查行号区间数值元组结构化与重合合并
- **测试标识**: `TC-WM-001`
- **测试目的**: 验证多次读取同一文件的不同行号区间时，底层数据结构自动合并重叠区间。
- **输入序列**: 先读 1~50 行，再读 40~100 行，再读 150~200 行。
- **预期结果**:
  - `_file_ranges` 自动合并为 `[(1, 100), (150, 200)]`；
  - 格式化展示为 `第 1 至 100 行; 第 150 至 200 行`；
  - 杜绝重复读取导致工作记忆文本急剧膨胀。
- **对应自动化测试**: `tests/test_context.py::TestContextEnhancements.test_point_14_inspected_file_range_merging_and_deduplication` 与 `test_point_19_working_memory_exact_numerical_tuple_ranges`

#### 用例 TC-WM-002: 代码正文含 Error/Exception 不误判失败
- **测试标识**: `TC-WM-002`
- **测试目的**: 验证当被阅读的代码正文中包含 `raise ValueError("Error")` 时，工作记忆不会将此次读取误判为读取失败。
- **预期结果**: 该文件依然正常记录入已排查代码清单。
- **对应自动化测试**: `tests/test_context.py::TestContextEnhancements.test_point_8_read_code_with_exception_not_mistaken_as_failure`

---

### 3.6 物理快照与原子回滚事务测试 (TC-SNAP)

#### 用例 TC-SNAP-001: 写前快照毫秒级备份 (Shadow Snapshot)
- **测试标识**: `TC-SNAP-001`
- **测试目的**: 验证文件首次修改前自动完成磁盘快照备份。
- **预期结果**: 快照目录生成时间戳版本，同一轮内多次修改锁定该轮初态。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestDiskSnapshotAndUndo.test_multi_modifications_in_same_turn_preserves_initial_state`

#### 用例 TC-SNAP-002: 物理 `/undo` 修改还原与新建文件清除
- **测试标识**: `TC-SNAP-002`
- **测试目的**: 验证输入 `/undo` 时物理磁盘完成真实还原。
- **预期结果**: 被改文件内容还原至初始版本，新建文件被物理删除。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestDiskSnapshotAndUndo.test_undo_restores_modified_file` 与 `test_undo_deletes_newly_created_file`

#### 用例 TC-SNAP-003: 多文件补丁事务原子性 (Patch Transaction)
- **测试标识**: `TC-SNAP-003`
- **测试目的**: 验证多文件补丁中途失败时，已修改的文件自动全量事务级回滚。
- **预期结果**: 文件 1 修改后，文件 2 报错 -> 文件 1 自动恢复初始内容，磁盘零脏数据。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestPatchToolEnhancements.test_multi_file_patch_transaction_atomicity`

---

### 3.7 项目级状态总线与全局用户画像测试 (TC-STATE)

#### 用例 TC-STATE-001: 项目物理目录分箱隔离
- **测试标识**: `TC-STATE-001`
- **测试目的**: 验证不同工程项目的会话历史物理隔离存储在 `history/<project>/`。
- **预期结果**: 会话日志、快照及 `project_state.json` 物理收敛于对应项目目录。
- **对应自动化测试**: `tests/test_session.py::TestProjectLevelStateAndFusionWorkingMemory.test_project_physical_directory_isolation`

#### 用例 TC-STATE-002: 跨会话融合工作记忆去重
- **测试标识**: `TC-STATE-002`
- **测试目的**: 验证同一工程多会话切换时，代码修改拓扑信息能够共享且不重复插入。
- **预期结果**: 工作区感知状态完美融合，排查无盲区。
- **对应自动化测试**: `tests/test_session.py::TestProjectLevelStateAndFusionWorkingMemory.test_cross_session_fusion_working_memory_no_duplication`

---

## 4. 工业级工具框架与内置工具箱测试套件 (Tools Framework & Builtin Tools)

### 4.1 增强补丁工具测试 (TC-PATCH)

#### 用例 TC-PATCH-001: 行号前缀容错剥离
- **测试标识**: `TC-PATCH-001`
- **测试输入**: SEARCH 块包含 `42 | def calculate(x):` 及 `43 |     return x * 2`。
- **预期结果**: 精准识别并剥离 `42 | ` 前缀，不误伤代码正文合法冒号与竖线，补丁成功打入。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestPatchToolEnhancements.test_line_number_prefix_stripping`

#### 用例 TC-PATCH-002: 保护代码中合法冒号不被剥离
- **测试标识**: `TC-PATCH-002`
- **测试输入**: 代码包含字典映射 `MAP = { 1: 'apple' }`。
- **预期结果**: 剥离算法精准定位开头的行号指示符，正文冒号完好无损保留，补丁无缝应用。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestPatchToolEnhancements.test_colon_in_code_not_accidentally_stripped`

#### 用例 TC-PATCH-003: Python AST 语法即时自检与语法错误阻断
- **测试标识**: `TC-PATCH-003`
- **测试输入**: 补丁引入语法错误（如括号未闭合 `def foo(): return (1 + `）。
- **预期结果**: `ast.parse` 校验抛出 `SyntaxError`，补丁工具自动执行事务回滚，向 Agent 输出包含错误行号的诊断提示。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestPatchToolEnhancements.test_python_ast_syntax_warning_and_rollback`

#### 用例 TC-PATCH-004: Windows CRLF 与 Linux LF 换行归一化
- **测试标识**: `TC-PATCH-004`
- **测试目的**: 验证跨平台换行符不匹配导致 SEARCH 块定位失败的问题已彻底根治。
- **预期结果**: CRLF 目标文件与 LF 补丁自动归一化匹配成功。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestPatchToolEnhancements.test_crlf_and_lf_normalization`

#### 用例 TC-PATCH-005: 模糊空白容错精准打补丁
- **测试标识**: `TC-PATCH-005`
- **测试输入**: 代码缩进或行尾空格存在微小差异。
- **预期结果**: 模糊容错匹配器成功定位目标上下文并完成修改。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestPatchToolEnhancements.test_fuzzy_patch_tolerance`

---

### 4.2 本地文件读写与大纲视图测试 (TC-FILE)

#### 用例 TC-FILE-001: view_file_outline AST 语法大纲提取
- **测试标识**: `TC-FILE-001`
- **测试目的**: 验证超长 Python 源码文件的 Class/Function/Method 定义及起止行号秒级提取。
- **预期结果**: 返回紧凑的大纲结构树，不产生大体量 Token 消耗。
- **对应自动化测试**: `tests/test_context.py::TestContextEnhancements.test_point_21_view_file_outline_ast_and_wm_integration`

#### 用例 TC-FILE-002: read_file 多字符集智能探测与容灾
- **测试标识**: `TC-FILE-002`
- **测试目的**: 验证 UTF-8、GBK、Latin-1、CP1252 编码文件自动识别与安全读取。
- **预期结果**: 正确呈现中文及特殊符号，绝不发生 `UnicodeDecodeError`。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestFileToolsEnhancements.test_read_file_auto_encoding`

#### 用例 TC-FILE-003: read_file 行号范围精准切片分页
- **测试标识**: `TC-FILE-003`
- **测试目的**: 验证大文件支持指定 `start_line` 与 `max_lines` 进行定向切片阅读。
- **预期结果**: 仅返回指定范围行内容，附带行号前缀，节省上下文空间。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestFileToolsEnhancements.test_read_file_line_range`

#### 用例 TC-FILE-004: write_file 写前快照与沙箱拦截
- **测试标识**: `TC-FILE-004`
- **测试目的**: 验证新建或全量写入文件时自动执行物理写前快照，且越界路径被坚决阻断。
- **预期结果**: 安全路径写入成功且快照入栈，危险越界路径抛出 `PermissionError`。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestFileToolsEnhancements.test_write_file_shadow_snapshot`

---

### 4.3 终端命令策略与人机审批测试 (TC-SHELL)

#### 用例 TC-SHELL-001: AUTO 模式免打扰与 ASK 模式弹窗
- **测试标识**: `TC-SHELL-001`
- **测试目的**: 验证类似 Claude Code 的全自动执行体验及人机交互审批。
- **预期结果**:
  - `auto` 模式下常见测试与构建命令直接放行；
  - `ask` 模式下弹窗呈现彩色命令卡片，支持 `[y/n/a]` 操作。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestClaudeAutoMode.test_auto_mode_allows_sensitive_and_complex_commands`

#### 用例 TC-SHELL-002: 高危破坏性命令无条件硬阻断
- **测试标识**: `TC-SHELL-002`
- **测试输入**: `rm -rf /`、`mkfs.ext4`、`format c:`、`dd if=/dev/zero`。
- **预期结果**: 无论在 AUTO 还是 ASK 模式，均判定为 `DENY`，强制拦截。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestClaudeAutoMode.test_auto_mode_still_blocks_high_risk_destructive_commands`

#### 用例 TC-SHELL-003: 复合命令链切分与换行符绕过防御
- **测试标识**: `TC-SHELL-003`
- **测试输入**: `pytest && rm -rf dist` 或 `git status \n dangerous_cmd`。
- **预期结果**: 命令被安全拆解为子单元，子单元命中黑名单时全链条阻断。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestCommandPolicyZeroFatigueAndDefense.test_command_chaining_bypass_strictly_blocked`

#### 用例 TC-SHELL-004: run_shell 指定工作目录安全执行
- **测试标识**: `TC-SHELL-004`
- **测试目的**: 验证指定 `cwd` 下执行命令的正确性与越界拦截。
- **预期结果**: 在目标子目录下正确运行，若工作目录超出沙箱则阻断。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestShellToolHardening.test_run_shell_with_cwd`

#### 用例 TC-SHELL-005: 终端命令超时保护阻断卡死
- **测试标识**: `TC-SHELL-005`
- **测试目的**: 验证执行无限循环脚本或挂起命令时超时自动杀掉子进程。
- **预期结果**: 触发超时，优雅回收子进程并返回超时提示，Agent 恢复正常交互。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestShellToolHardening.test_shell_timeout`

---

### 4.4 语义输出优化与磁盘溢出落盘测试 (TC-CLAMP)

#### 用例 TC-CLAMP-001: Shell 测试报错 Traceback 智能保全
- **测试标识**: `TC-CLAMP-001`
- **测试目的**: 验证长达 50k 字符的测试输出截断时，末尾关键的 `FAILED` 与 Traceback 完整保留。
- **预期结果**: 截断器智能提取头部与尾部核心错误，不发生信息盲目丢失。
- **对应自动化测试**: `tests/test_output_optimization_and_tool_precision.py::TestSpoolingAndOutputOptimization.test_clamp_shell_output_preserves_traceback_and_failures`

#### 用例 TC-CLAMP-002: 巨型输出落盘至 history/.spool/ 与透镜提示
- **测试标识**: `TC-CLAMP-002`
- **测试目的**: 验证输出溢出时自动写入临时转储文件并提供追踪透镜提示。
- **预期结果**: 生成 `.spool` 文件，工具结果附带 `[系统提示: 完整原始输出已落盘...]`。
- **对应自动化测试**: `tests/test_output_optimization_and_tool_precision.py::TestSpoolingAndOutputOptimization.test_disk_spooling_creates_file_and_lens_hint`

#### 用例 TC-CLAMP-003: 检索工具滥用拦截与专用工具重定向
- **测试标识**: `TC-CLAMP-003`
- **测试目的**: 验证 Agent 尝试通过 `run_shell(cat/grep/find)` 违规执行时，引导重定向至专用文件与检索工具。
- **预期结果**: 返回友好的系统重定向提示，提升工具调用的规范性与跨平台稳定性。
- **对应自动化测试**: `tests/test_output_optimization_and_tool_precision.py::TestToolSelectionPrecision.test_shell_misuse_redirector_cat_head_tail`

---

## 5. MCP 外部扩展与 Skills 生态测试套件 (MCP & Skills Subsystem)

### 5.1 MCP 外部扩展测试 (TC-MCP)

#### 用例 TC-MCP-001: 多级级联配置扫描与项目级覆盖
- **测试标识**: `TC-MCP-001`
- **测试目的**: 验证项目专属 `.super/mcp_servers.json` 优先于用户全局配置。
- **预期结果**: 成功合并配置，项目级同名服务覆盖全局同名服务。
- **对应自动化测试**: `tests/test_mcp.py::TestMcpIntegration.test_cascade_config_discovery_and_dual_base_resolution`

#### 用例 TC-MCP-002: Stderr 管道防死锁与进程异常自愈
- **测试标识**: `TC-MCP-002`
- **测试目的**: 验证外部 MCP 服务持续写入大量 stderr 时不阻塞主进程，握手失败立即清理销毁子进程。
- **预期结果**: 异步守护线程持续读取 stderr，握手失败子进程被即时 kill，无孤儿进程残留。
- **对应自动化测试**: `tests/test_mcp.py::TestMcpIntegration.test_stderr_pipe_deadlock_prevention` 与 `test_manager_handshake_failure_cleanup`

#### 用例 TC-MCP-003: MCP 外部服务工具发现与闭环调用
- **测试标识**: `TC-MCP-003`
- **测试目的**: 验证通过 JSON-RPC 2.0 成功发现外部注册的计算工具（如 `calculate_stats`）并完成闭环执行。
- **预期结果**: 工具成功注册至全局工具箱，Agent 发起调用并正确获取 JSON-RPC 返回结果。
- **对应自动化测试**: `tests/test_mcp.py::TestMcpIntegration.test_mcp_calc_server_discovery_and_execution`

#### 用例 TC-MCP-004: 工具重名遮蔽防护 (Tool Shadowing Prevention)
- **测试标识**: `TC-MCP-004`
- **测试目的**: 验证外部 MCP 服务若试图注册与内置核心工具（如 `apply_patch`、`read_file`）重名的工具时，系统能主动重命名或拒绝，防止内核工具被恶意遮蔽。
- **预期结果**: 核心内置工具优先级锁定，外部工具自动加前缀隔离。
- **对应自动化测试**: `tests/test_mcp.py::TestMcpIntegration.test_tool_shadowing_prevention`

#### 用例 TC-MCP-005: 外部子进程环境变量白名单脱敏
- **测试标识**: `TC-MCP-005`
- **测试目的**: 验证启动外部 MCP 子进程时，核心 LLM API 密钥等敏感变量被安全过滤，不泄露至未受信任的子进程。
- **预期结果**: 子进程仅接收白名单环境变量。
- **对应自动化测试**: `tests/test_mcp.py::TestMcpIntegration.test_env_sanitization`

---

### 5.2 Skills 专家技能包测试 (TC-SKILL)

#### 用例 TC-SKILL-001: YAML Frontmatter 解析与多级扫描
- **测试标识**: `TC-SKILL-001`
- **测试目的**: 验证 `.skills/` 目录下技能包的元数据解析与级联发现。
- **预期结果**: 成功解析 `name`, `description`, `scope` 等字段。
- **对应自动化测试**: `tests/test_skills.py::TestSkillsSubsystem.test_skill_frontmatter_parsing`

#### 用例 TC-SKILL-002: 渐进式披露 (Progressive Disclosure)
- **测试标识**: `TC-SKILL-002`
- **测试目的**: 验证默认仅向系统提示词注入轻量技能索引，按需加载完整 SOP。
- **预期结果**: 初始 System Prompt 仅占用极少 Tokens，在激活时展开详细规则。
- **对应自动化测试**: `tests/test_skills.py::TestSkillsSubsystem.test_progressive_disclosure_prompts`

#### 用例 TC-SKILL-003: 专家技能外部安装器
- **测试标识**: `TC-SKILL-003`
- **测试目的**: 验证从 GitHub 仓库或本地目录一键安装专家技能包并即时重载生效。
- **预期结果**: 技能文件被安全放置至 `.skills/` 目录，`SkillManager` 动态更新索引。
- **对应自动化测试**: `tests/test_skills.py::TestSkillsSubsystem.test_skill_installer`

---

## 6. CLI 控制台、会话生命周期与人机协同测试套件 (CLI & Session Lifecycle)

### 6.1 多会话管理与跨工程隔离测试 (TC-SESS)

#### 用例 TC-SESS-001: 多会话隔离、新建、删除与重命名
- **测试标识**: `TC-SESS-001`
- **测试目的**: 验证完整的会话生命周期 CRUD 操作及其磁盘落盘隔离。
- **预期结果**: 会话独立归档于 `history/<project>/<session_id>.json`，重命名与删除同步更新物理文件。
- **对应自动化测试**: `tests/test_session.py::TestMultiSessionManagement.test_create_and_delete_session` 与 `test_rename_session_and_disk_migration`

#### 用例 TC-SESS-002: 多会话动态无缝切换与历史恢复 (`/switch`)
- **测试标识**: `TC-SESS-002`
- **测试目的**: 验证会话即时持久化与切换恢复。
- **预期结果**: 切换时当前会话落盘，目标会话恢复 Working Memory 与历史快照。
- **对应自动化测试**: `tests/test_session.py::TestMultiSessionManagement.test_multi_session_auto_restore_on_switch`

#### 用例 TC-SESS-003: `/cd` 切换工作区联动会话管理器
- **测试标识**: `TC-SESS-003`
- **测试目的**: 验证在控制台输入 `/cd <路径>` 时，系统自动重置当前工作区根目录并重新绑定项目级会话目录。
- **预期结果**: 工作区平滑迁移，历史物理路径即时刷新。
- **对应自动化测试**: `tests/test_session.py::TestMultiSessionManagement.test_switch_workspace_and_cd_command`

---

### 6.2 用户全局记忆与控制台命令测试 (TC-CMD)

#### 用例 TC-CMD-001: 斜杠指令集分发与帮助呈现
- **测试标识**: `TC-CMD-001`
- **测试目的**: 验证所有内置斜杠指令（`/status`, `/skills`, `/mcp`, `/undo`, `/reset`, `/help` 等）能够正确分发处理。
- **预期结果**: 格式化呈现清晰明了的控制台指令卡片。
- **对应自动化测试**: `tests/test_cli_ui.py::TestClaudeCodeUI.test_help_table`

#### 用例 TC-CMD-002: 跨项目永久用户偏好记录与注入 (`/remember`)
- **测试标识**: `TC-CMD-002`
- **测试输入**: `/remember 必须使用严格类型标注与 Google 风格 Docstring`。
- **预期结果**:
  1. 写入 `~/.super-harnes/global_memory.json`；
  2. 新启动的项目与会话中，System Prompt 自动包含该全局注记。
- **对应自动化测试**: `tests/test_session.py::TestGlobalUserMemory.test_cli_global_memory_commands`

---

### 6.3 Rich 终端渲染与人机审批测试 (TC-UI)

#### 用例 TC-UI-001: 用户交互确认与 EOF 安全拒绝
- **测试标识**: `TC-UI-001`
- **测试目的**: 验证在敏感命令审批时呈现彩色卡片，在交互终端输入 `y` 放行，无交互或输入流关闭 (EOF) 时默认安全拒绝。
- **预期结果**: 批准则继续执行，EOF 终止并返回拒绝提示，绝不静默放行。
- **对应自动化测试**: `tests/test_cli_ui.py::TestClaudeCodeUI.test_approval_prompt_approved` 与 `test_approval_prompt_auto_reject_on_eof`

#### 用例 TC-UI-002: 彩色统一 Diff 与思维链折叠呈现
- **测试标识**: `TC-UI-002`
- **测试目的**: 验证打补丁时控制台呈现红绿双色 Unified Diff 卡片，大模型 Thinking 过程支持折叠展示。
- **预期结果**: 渲染整洁美观，大幅提升终端开发者体验。
- **对应自动化测试**: `tests/test_cli_ui.py::TestClaudeCodeUI.test_tool_card_rendering_patch` 与 `test_thinking_rendering`

---

## 7. 高级非功能性与鲁棒性防御测试套件 (Advanced Robustness & Security)

### 7.1 安全沙箱穿透与逃逸拦截测试 (TC-SEC)

#### 用例 TC-SEC-001: 路径穿越深度防御与跨盘符非法访问拦截
- **测试标识**: `TC-SEC-001`
- **测试输入**: Agent 尝试读取或写入包含 `../`、`..\\..` 或跨盘符绝对路径（如 `C:\\Windows\\System32`）。
- **预期结果**: 沙箱边界防御器触发，抛出 `PermissionError`，拦截所有工作区外物理访问。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestDynamicWorkspace.test_conditional_core_protected_files`

#### 用例 TC-SEC-002: 敏感资产与内核防御代码自保护
- **测试标识**: `TC-SEC-002`
- **测试输入**: 补丁目标指向 `.env`, `.git`, `.venv`, `tools/builtin/patch_tool.py`。
- **预期结果**: 核心自保护规则拦截，禁止代码篡改防御机制本身。
- **对应自动化测试**: `tests/test_local_terminal_tools.py::TestDynamicWorkspace.test_conditional_core_protected_files`

---

### 7.2 极端边界与容灾压测 (TC-STRESS)

#### 用例 TC-STRESS-001: 500,000 Tokens 极端长程会话持续推理
- **测试标识**: `TC-STRESS-001`
- **测试场景**: 模拟 50 轮连续高密度代码排查，Token 累计触达 Tier 3 上限（500k）。
- **预期结果**:
  1. 账本按需自适应跃迁至 500k；
  2. 水位管理在绿黄红三区间自适应调节，及时生成增量摘要；
  3. 内存稳定，无句柄泄漏与进程僵死。

---

### 7.3 异常中断与进程恢复测试 (TC-RECOVER)

#### 用例 TC-RECOVER-001: 历史文件异常损坏自愈与优雅回退
- **测试标识**: `TC-RECOVER-001`
- **测试场景**: 会话历史 JSON 文件中途被非正常关机破坏导致部分语法解析失败。
- **预期结果**: 恢复引擎具备容灾校验，隔离损坏条目，保留可用历史并向控制台提示警告，避免 Agent 启动崩溃。

---

## 8. 端到端与真实软件工程场景回归测试套件 (E2E & SWE Scenarios)

### 8.1 典型 SWE 单文件缺陷修复闭环 (TC-E2E-01)
- **场景描述**: 模拟一个带有 Off-by-one 错误的排序模块 `sort_util.py` 及其测试用例 `test_sort.py`。
- **执行闭环流程**:
  1. **User**: `"修复 test_sort.py 中失败的用例并确保全量测试通过"`；
  2. **Step 1 (EXPLORE)**: Agent 自动调用 `run_shell(pytest test_sort.py)` 捕获失败断言；
  3. **Step 2 (EXPLORE)**: Agent 调用 `read_file(sort_util.py)` 定位循环边界条件；
  4. **Step 3 (MODIFY)**: Agent 调用 `apply_patch` 精准修改边界比较操作符；
  5. **Step 4 (VERIFY)**: 阶段机自动重排置顶 `run_shell`，Agent 执行 `pytest` 确认全绿；
  6. **Step 5 (Wrap-up)**: Agent 输出修复总结与根因说明。
- **断言指标**: 任务总步数 <= 6 步，AST 检查无误，Git Diff 最小化，测试 100% 通过。

### 8.2 多文件架构重构与测试回归 (TC-E2E-02)
- **场景描述**: 模拟重构数据访问层，涉及接口定义、实现类与业务调用的多文件原子改动。
- **验证重点**: 多文件补丁事务原子性、写前快照备份、项目级修改拓扑同步沉淀。

### 8.3 外部 MCP 工具协同复杂计算与系统自检 (TC-E2E-03)
- **场景描述**: 挂载外部 MCP 统计服务，Agent 自动调用外部服务聚合工程统计数据并输出可视化报告。
- **验证重点**: JSON-RPC 2.0 stdio 协议握手、并发子进程管理、退出时安全清理。

---

## 9. 自动化测试执行指南与 CI/CD 质量门禁 (Execution & CI/CD)

### 9.1 全量测试运行与快速调试

```bash
# 激活工程专属虚拟环境
.venv\Scripts\activate  # Windows
source .venv/bin/activate # Linux / macOS

# 1. 运行一键全量回归测试套件 (包含全部 145 项核心测试)
python scripts/run_checks.py

# 2. 运行单模块测试 (支持高精度排查与单元调优)
python -m unittest tests/test_context.py
python -m unittest tests/test_local_terminal_tools.py
python -m unittest tests/test_loop_detector.py
python -m unittest tests/test_mcp.py
python -m unittest tests/test_output_optimization_and_tool_precision.py
python -m unittest tests/test_session.py
python -m unittest tests/test_skills.py
python -m unittest tests/test_cli_ui.py
```

### 9.2 全量 145 项回归测试清单全表

| 测试用例函数全名 | 所属模块 | 验证关键特性 | 状态 |
| :--- | :--- | :--- | :---: |
| `test_cli_ui.TestClaudeCodeUI.test_approval_prompt_approved` | MOD-CLI | 用户确认批准交互流 | PASS |
| `test_cli_ui.TestClaudeCodeUI.test_approval_prompt_auto_reject_on_eof` | MOD-CLI | EOF 默认安全拒绝 | PASS |
| `test_cli_ui.TestClaudeCodeUI.test_assistant_markdown_response` | MOD-CLI | Markdown 富文本排版渲染 | PASS |
| `test_cli_ui.TestClaudeCodeUI.test_banner_rendering` | MOD-CLI | 启动 Banner 元数据呈现 | PASS |
| `test_cli_ui.TestClaudeCodeUI.test_help_table` | MOD-CLI | /help 指令表格美化 | PASS |
| `test_cli_ui.TestClaudeCodeUI.test_interactive_command_palette_fallback` | MOD-CLI | 交互式命令面板降级兜底 | PASS |
| `test_cli_ui.TestClaudeCodeUI.test_sessions_table` | MOD-CLI | 会话列表卡片渲染 | PASS |
| `test_cli_ui.TestClaudeCodeUI.test_thinking_rendering` | MOD-CLI | 模型思维链动态折叠 | PASS |
| `test_cli_ui.TestClaudeCodeUI.test_token_usage_rendering` | MOD-CLI | 实时 Token 仪表盘呈现 | PASS |
| `test_cli_ui.TestClaudeCodeUI.test_tool_card_rendering_bash` | MOD-CLI | Shell 工具调用彩色卡片 | PASS |
| `test_cli_ui.TestClaudeCodeUI.test_tool_card_rendering_patch` | MOD-CLI | 补丁 Diff 语法高亮卡片 | PASS |
| `test_cli_ui.TestClaudeCodeUI.test_user_prompt_rendering` | MOD-CLI | 用户输入面板规范 | PASS |
| `test_context.TestContextEnhancements.test_point_1_system_prompt_immutability` | MOD-CORE | System 提示词绝对不可变 | PASS |
| `test_context.TestContextEnhancements.test_point_2_budget_ledger_allocation` | MOD-CTX | 200k 专款专用分账账本 | PASS |
| `test_context.TestContextEnhancements.test_point_3_summary_range_tracking` | MOD-CTX | 摘要轮次区间精准锚定 | PASS |
| `test_context.TestContextEnhancements.test_point_4_anti_jitter_debounce` | MOD-CTX | 阶梯扩缩容防抖冷却 | PASS |
| `test_context.TestContextEnhancements.test_point_5_budget_ledger_validation_and_dynamic_recalc` | MOD-CTX | 账本参数动态重算校验 | PASS |
| `test_context.TestContextEnhancements.test_point_6_token_counter_precision_and_structures` | MOD-CTX | tiktoken 高精度分词统计 | PASS |
| `test_context.TestContextEnhancements.test_point_7_watermark_dynamic_recovery_from_red_zone` | MOD-CTX | 红区摘要后动态回退绿区 | PASS |
| `test_context.TestContextEnhancements.test_point_8_read_code_with_exception_not_mistaken_as_failure` | MOD-TOOL | 代码中含 Error 词不误判失败 | PASS |
| `test_context.TestContextEnhancements.test_point_9_green_zone_no_duplicate_injection` | MOD-CTX | 绿区全量直通零损耗 | PASS |
| `test_context.TestContextEnhancements.test_point_10_prompt_cache_friendly_working_memory_position` | MOD-CORE | 记忆注入位置保障 Cache 命中 | PASS |
| `test_context.TestContextEnhancements.test_point_11_apply_patch_tool_exact_recognition` | MOD-TOOL | 补丁成功标识精准匹配 | PASS |
| `test_context.TestContextEnhancements.test_point_12_hard_gatekeeper_user_wm_compression` | MOD-CTX | 极端硬门禁保护性压缩 | PASS |
| `test_context.TestContextEnhancements.test_point_13_react_inturn_dynamic_circuit_breaker` | MOD-CORE | 轮内步间动态预算熔断 | PASS |
| `test_context.TestContextEnhancements.test_point_14_inspected_file_range_merging_and_deduplication` | MOD-CTX | 排查文件区间重合智能合并 | PASS |
| `test_context.TestContextEnhancements.test_point_15_log_compaction_and_vacuum` | MOD-CTX | 会话日志压缩与清理 | PASS |
| `test_context.TestContextEnhancements.test_point_16_ground_truth_api_usage_tracking` | MOD-CTX | 真实 API 计费统计对齐 | PASS |
| `test_context.TestContextEnhancements.test_point_17_goal_intent_prefix_trimming_and_heuristics` | MOD-CORE | 目标意图前缀精简提取 | PASS |
| `test_context.TestContextEnhancements.test_point_18_yellow_and_red_zone_candidate_deduplication` | MOD-CTX | 黄红区候选轮次智能去重 | PASS |
| `test_context.TestContextEnhancements.test_point_19_working_memory_exact_numerical_tuple_ranges` | MOD-CTX | 行号区间数值元组结构化 | PASS |
| `test_context.TestContextEnhancements.test_point_20_cli_status_token_usage_display` | MOD-CLI | /status 实时呈现账本阶梯 | PASS |
| `test_context.TestContextEnhancements.test_point_21_view_file_outline_ast_and_wm_integration` | MOD-TOOL | AST 大纲与工作记忆联动 | PASS |
| `test_context.TestContextEnhancements.test_point_22_step_awareness_and_graceful_wrapup` | MOD-CORE | 步数耗尽自动平滑收尾 | PASS |
| `test_context.TestContextEnhancements.test_point_23_dynamic_budget_ledger_200k_default_and_elastic_expansion` | MOD-CTX | 200k~500k 弹性扩容 | PASS |
| `test_context.TestContextEnhancements.test_point_24_write_file_and_fuzzy_patch_tolerance` | MOD-TOOL | 模糊补丁与全写容错 | PASS |
| `test_context.TestContextEnhancements.test_point_25_elastic_context_watermark_and_agent_inturn_expansion` | MOD-CTX | 水位与轮内扩容无缝联动 | PASS |
| `test_context.TestContextEnhancements.test_point_25_inturn_observation_pruning` | MOD-CORE | 轮内旧长输出折叠 | PASS |
| `test_context.TestContextEnhancements.test_point_26_console_inherits_agent_max_steps` | MOD-CLI | 控制台统一继承步数上限 | PASS |
| `test_context.TestContextEnhancements.test_point_27_working_memory_turn_id_and_expanded_file_display` | MOD-CTX | 工作记忆记录修改轮次 ID | PASS |
| `test_local_terminal_tools.TestClaudeAutoMode.test_auto_mode_allows_sensitive_and_complex_commands` | MOD-TOOL | AUTO 模式放行常规命令 | PASS |
| `test_local_terminal_tools.TestClaudeAutoMode.test_auto_mode_request_approval_returns_true_immediately` | MOD-TOOL | AUTO 模式非阻塞放行 | PASS |
| `test_local_terminal_tools.TestClaudeAutoMode.test_auto_mode_still_blocks_high_risk_destructive_commands` | MOD-TOOL | AUTO 模式依然坚决阻断高危 | PASS |
| `test_local_terminal_tools.TestClaudeAutoMode.test_default_policy_defaults_to_auto` | MOD-TOOL | 生产环境默认采用 AUTO 模式 | PASS |
| `test_local_terminal_tools.TestClaudeAutoMode.test_slash_command_mode_switching` | MOD-CLI | /auto 与 /ask 指令即时生效 | PASS |
| `test_local_terminal_tools.TestCommandPolicyZeroFatigueAndDefense.test_command_chaining_bypass_strictly_blocked` | MOD-TOOL | 复合命令链注入攻击拦截 | PASS |
| `test_local_terminal_tools.TestCommandPolicyZeroFatigueAndDefense.test_dangerous_commands_denied` | MOD-TOOL | 危险命令黑名单坚决阻断 | PASS |
| `test_local_terminal_tools.TestCommandPolicyZeroFatigueAndDefense.test_mutating_commands_require_approval` | MOD-TOOL | 变更类命令在 ASK 下弹窗 | PASS |
| `test_local_terminal_tools.TestCommandPolicyZeroFatigueAndDefense.test_safe_test_and_lint_commands_allowed` | MOD-TOOL | 只读与测试命令零打扰放行 | PASS |
| `test_local_terminal_tools.TestDiskSnapshotAndUndo.test_multi_modifications_in_same_turn_preserves_initial_state` | MOD-CTX | 同轮多次改动锁定初始快照 | PASS |
| `test_local_terminal_tools.TestDiskSnapshotAndUndo.test_undo_deletes_newly_created_file` | MOD-CTX | /undo 物理级删除新建文件 | PASS |
| `test_local_terminal_tools.TestDiskSnapshotAndUndo.test_undo_restores_modified_file` | MOD-CTX | /undo 物理级无损还原修改 | PASS |
| `test_local_terminal_tools.TestDynamicWorkspace.test_conditional_core_protected_files` | MOD-SEC | 核心防御模块自身代码保护 | PASS |
| `test_local_terminal_tools.TestDynamicWorkspace.test_dynamic_history_dir_redirection` | MOD-CTX | 工作区动态重定向历史目录 | PASS |
| `test_local_terminal_tools.TestDynamicWorkspace.test_workspace_switch_and_isolation` | MOD-CTX | 工作区物理切换与严格隔离 | PASS |
| `test_local_terminal_tools.TestPatchToolEnhancements.test_colon_in_code_not_accidentally_stripped` | MOD-TOOL | 保护代码中合法冒号不被剥离 | PASS |
| `test_local_terminal_tools.TestPatchToolEnhancements.test_line_number_prefix_stripping` | MOD-TOOL | 容错剥离 IDE 复制的行号 | PASS |
| `test_local_terminal_tools.TestPatchToolEnhancements.test_multi_file_patch_transaction_atomicity` | MOD-TOOL | 多文件补丁事务全原子性 | PASS |
| `test_local_terminal_tools.TestPatchToolEnhancements.test_python_ast_syntax_warning_and_rollback` | MOD-TOOL | AST 语法预检失败自动回滚 | PASS |
| `test_local_terminal_tools.TestPatchToolEnhancements.test_crlf_and_lf_normalization` | MOD-TOOL | CRLF 与 LF 跨平台换行归一 | PASS |
| `test_local_terminal_tools.TestPatchToolEnhancements.test_fuzzy_patch_tolerance` | MOD-TOOL | 模糊空白容错精准打补丁 | PASS |
| `test_local_terminal_tools.TestFileToolsEnhancements.test_read_file_auto_encoding` | MOD-TOOL | UTF-8/GBK 自动编码解码 | PASS |
| `test_local_terminal_tools.TestFileToolsEnhancements.test_read_file_line_range` | MOD-TOOL | 按行区间分页精准读取 | PASS |
| `test_local_terminal_tools.TestFileToolsEnhancements.test_write_file_shadow_snapshot` | MOD-TOOL | 全写文件前自动物理快照 | PASS |
| `test_local_terminal_tools.TestShellToolHardening.test_run_shell_with_cwd` | MOD-TOOL | 指定工作目录执行子命令 | PASS |
| `test_local_terminal_tools.TestShellToolHardening.test_shell_timeout` | MOD-TOOL | 终端命令超时保护阻断卡死 | PASS |
| `test_loop_detector.TestLoopDetector.test_mode_1_consecutive_duplicate_calls` | MOD-CORE | 模式1: 连续完全同参调用检测 | PASS |
| `test_loop_detector.TestLoopDetector.test_mode_2_oscillating_ping_pong_cycles` | MOD-CORE | 模式2: 多工具震荡死循环识别 | PASS |
| `test_loop_detector.TestLoopDetector.test_mode_3_consecutive_identical_errors` | MOD-CORE | 模式3: 连续相同报错停滞检测 | PASS |
| `test_loop_detector.TestUnboundedReActExecution.test_unbounded_mode_force_wrapup_on_dead_loop` | MOD-CORE | 自主排查遇死循环强制脱困 | PASS |
| `test_loop_detector.TestUnboundedReActExecution.test_unbounded_mode_natural_exit_when_no_tool_calls` | MOD-CORE | 无工具调用自然完成退出 | PASS |
| `test_mcp.TestMcpIntegration.test_cascade_config_discovery_and_dual_base_resolution` | MOD-MCP | 级联发现项目级 MCP 配置 | PASS |
| `test_mcp.TestMcpIntegration.test_env_sanitization` | MOD-MCP | 外部进程环境变量安全脱敏 | PASS |
| `test_mcp.TestMcpIntegration.test_manager_handshake_failure_cleanup` | MOD-MCP | 握手失败即时回收孤儿进程 | PASS |
| `test_mcp.TestMcpIntegration.test_mcp_calc_server_discovery_and_execution` | MOD-MCP | MCP 外部计算工具调用闭环 | PASS |
| `test_mcp.TestMcpIntegration.test_mcp_manager_config_loading` | MOD-MCP | JSON 配置正向与异常解析 | PASS |
| `test_mcp.TestMcpIntegration.test_project_level_mcp_config_override_and_merge` | MOD-MCP | 项目级配置覆盖合并全局配置 | PASS |
| `test_mcp.TestMcpIntegration.test_semantic_output_clamping_with_huge_errors` | MOD-MCP | 语义截断超长 MCP 报错 | PASS |
| `test_mcp.TestMcpIntegration.test_spool_file_rotation` | MOD-MCP | 临时转储文件生命周期轮转 | PASS |
| `test_mcp.TestMcpIntegration.test_stderr_pipe_deadlock_prevention` | MOD-MCP | 异步排空 Stderr 杜绝死锁 | PASS |
| `test_mcp.TestMcpIntegration.test_tool_shadowing_prevention` | MOD-MCP | 禁止外部工具重名遮蔽内核 | PASS |
| `test_output_optimization_and_tool_precision.TestSpoolingAndOutputOptimization.test_agent_protect_tool_result_watermark_linkage` | MOD-TOOL | 工具输出保护联动上下文水位 | PASS |
| `test_output_optimization_and_tool_precision.TestSpoolingAndOutputOptimization.test_anchor_indexed_lens_generation` | MOD-TOOL | 生成锚点检索透镜导航 | PASS |
| `test_output_optimization_and_tool_precision.TestSpoolingAndOutputOptimization.test_clamp_search_output_frequency_aggregation` | MOD-TOOL | 检索超长输出频次聚合呈现 | PASS |
| `test_output_optimization_and_tool_precision.TestSpoolingAndOutputOptimization.test_clamp_shell_output_preserves_traceback_and_failures` | MOD-TOOL | Shell 截断智能保留关键报错 | PASS |
| `test_output_optimization_and_tool_precision.TestSpoolingAndOutputOptimization.test_disk_spooling_creates_file_and_lens_hint` | MOD-TOOL | 超大输出磁盘溢出落盘与提示 | PASS |
| `test_output_optimization_and_tool_precision.TestSpoolingAndOutputOptimization.test_dynamic_watermark_quota_allocation` | MOD-TOOL | 绿黄红水位动态配额控制 | PASS |
| `test_output_optimization_and_tool_precision.TestSpoolingAndOutputOptimization.test_read_file_outline_augmented_fallback` | MOD-TOOL | 读大文件引导使用大纲工具 | PASS |
| `test_output_optimization_and_tool_precision.TestSpoolingAndOutputOptimization.test_stage_manager_lifecycle_and_reordering` | MOD-CORE | 阶段状态机流转与工具重排 | PASS |
| `test_output_optimization_and_tool_precision.TestToolSelectionPrecision.test_prompt_decision_matrix_injected` | MOD-CORE | 工具选择决策矩阵注入 Prompt | PASS |
| `test_output_optimization_and_tool_precision.TestToolSelectionPrecision.test_schema_negative_constraints_present` | MOD-CORE | 工具 Schema 显式注入负向约束 | PASS |
| `test_output_optimization_and_tool_precision.TestToolSelectionPrecision.test_shell_misuse_redirector_cat_head_tail` | MOD-TOOL | 拦截 run_shell(cat/head/tail) 重定向专用读工具 | PASS |
| `test_output_optimization_and_tool_precision.TestToolSelectionPrecision.test_shell_misuse_redirector_grep_and_find` | MOD-TOOL | 拦截 run_shell(grep/find) 重定向专用检索工具 | PASS |
| `test_output_optimization_and_tool_precision.TestToolSelectionPrecision.test_shell_valid_commands_allowed` | MOD-TOOL | 合法构建/测试命令正常放行 | PASS |
| `test_session.TestGlobalUserMemory.test_cli_global_memory_commands` | MOD-STATE | /remember 与 /forget 指令 | PASS |
| `test_session.TestGlobalUserMemory.test_context_construction_full_order` | MOD-CTX | 全局记忆安全注入上下文尾部 | PASS |
| `test_session.TestGlobalUserMemory.test_global_memory_persistence_and_habits` | MOD-STATE | 全局偏好画像落盘与恢复 | PASS |
| `test_session.TestGlobalUserMemory.test_project_registry_and_lookup` | MOD-STATE | 跨项目工作区检索与地图建立 | PASS |
| `test_session.TestMultiSessionManagement.test_agent_session_delegation_and_setter` | MOD-CLI | Agent 会话管理器委托属性 | PASS |
| `test_session.TestMultiSessionManagement.test_cli_slash_commands_multi_session` | MOD-CLI | 斜杠指令操作多会话 CRUD | PASS |
| `test_session.TestMultiSessionManagement.test_create_and_delete_session` | MOD-CLI | 独立会话创建、物理删除 | PASS |
| `test_session.TestMultiSessionManagement.test_get_session_preview_formatting` | MOD-CLI | 会话上下文快照卡片美化 | PASS |
| `test_session.TestMultiSessionManagement.test_multi_session_auto_restore_on_switch` | MOD-CLI | 切换会话时自动从磁盘热重载 | PASS |
| `test_session.TestMultiSessionManagement.test_multi_session_strict_isolation` | MOD-CLI | 多会话间记忆完全物理隔离 | PASS |
| `test_session.TestMultiSessionManagement.test_react_inturn_prompt_cache_strict_append_only` | MOD-CORE | 轮内单调追加保障 KV Cache | PASS |
| `test_session.TestMultiSessionManagement.test_rename_session_and_disk_migration` | MOD-CLI | 会话物理重命名与文件迁移 | PASS |
| `test_session.TestMultiSessionManagement.test_switch_workspace_and_cd_command` | MOD-CLI | /cd 切换工作区联动会话管理器 | PASS |
| `test_session.TestProjectLevelStateAndFusionWorkingMemory.test_cross_session_fusion_working_memory_no_duplication` | MOD-STATE | 跨会话融合工作记忆去重 | PASS |
| `test_session.TestProjectLevelStateAndFusionWorkingMemory.test_long_term_summary_strict_isolation_between_sessions` | MOD-CTX | 长期摘要保持会话级严格隔离 | PASS |
| `test_session.TestProjectLevelStateAndFusionWorkingMemory.test_project_physical_directory_isolation` | MOD-STATE | 项目级物理分箱收敛 history/ | PASS |
| `test_session.TestProjectLevelStateAndFusionWorkingMemory.test_project_state_rollback_synchronization` | MOD-STATE | /undo 联动项目总线撤销登记 | PASS |
| `test_session.TestSafeSlidingWindowAndSession.test_all_system_messages_at_head_for_api_compatibility` | MOD-CTX | 所有 System 消息置顶防 400 | PASS |
| `test_session.TestSafeSlidingWindowAndSession.test_disk_restore_isolates_uncompleted_turns` | MOD-CTX | 磁盘恢复严格隔离未完结轮次 | PASS |
| `test_session.TestSafeSlidingWindowAndSession.test_full_disk_persistence_with_summary_and_wm_restore` | MOD-CTX | 完整还原摘要状态与工作记忆 | PASS |
| `test_session.TestSafeSlidingWindowAndSession.test_hard_gatekeeper_enforces_output_reserve` | MOD-CTX | 严守 8000 Tokens 输出预留 | PASS |
| `test_session.TestSafeSlidingWindowAndSession.test_init_turn_counter_resets_on_session_cleared` | MOD-CTX | 会话重置时轮次计数重置为 1 | PASS |
| `test_session.TestSafeSlidingWindowAndSession.test_restore_from_disk_rebuilds_snapshot_stack_for_undo` | MOD-CTX | 恢复时完整重建快照栈以撤销 | PASS |
| `test_session.TestSafeSlidingWindowAndSession.test_rollback_disk_restoration_alignment` | MOD-CTX | 回滚落盘对齐记忆精准退栈 | PASS |
| `test_session.TestSafeSlidingWindowAndSession.test_sliding_window_strict_continuity_no_perforation` | MOD-CTX | 滑窗严格时间连续杜绝穿孔 | PASS |
| `test_session.TestSafeSlidingWindowAndSession.test_turn_chunk_atomic_pairing_and_sanitization` | MOD-CTX | 原子轮次双向成对清洗防孤儿 | PASS |
| `test_skills.TestSkillsSubsystem.test_skill_frontmatter_parsing` | MOD-SKILL | YAML Frontmatter 规范提取 | PASS |
| `test_skills.TestSkillsSubsystem.test_progressive_disclosure_prompts` | MOD-SKILL | 技能元数据轻量披露节约Token | PASS |
| `test_skills.TestSkillsSubsystem.test_cascade_candidate_discovery` | MOD-SKILL | 工作区/用户级/全局级联扫描 | PASS |
| `test_skills.TestSkillsSubsystem.test_skill_installer` | MOD-SKILL | 本地与远程技能包安全安装 | PASS |

---

### 9.3 GitHub Actions 流水线自动化门禁

在 `.github/workflows/ci.yml` 中配置了工业级持续集成门禁，确保每一项提交均满足质量基线：

```yaml
name: Super-Harnes Regression Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
        
    - name: Install Dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        
    - name: Run Full Regression Tests (145 items)
      run: |
        python scripts/run_checks.py
```

---

> **质量全景总结**: Super-Harnes 自动化测试体系从底层 AST 语法树自检、中层 MCP 零端口分布式协议交互到顶层 200k~500k 弹性滑窗，构建了坚不可摧的立体化质量防护网。145 项核心测试 100% 稳定通过，奠定了工业级 Autonomous Coding Agent 的工程交付基石！
