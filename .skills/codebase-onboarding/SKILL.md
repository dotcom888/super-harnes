---
name: codebase-onboarding
description: 面向陌生或已有项目的快速逆向架构摸底与核心代码定位 SOP。适用于“接手已有项目”、“梳理项目主流程骨架”、“为二次开发寻找模块接缝与核心代码”等场景。
---

# Codebase Onboarding & Core Flow Mapping (已有项目快速摸底与二次开发定位规约)

当你首次进入一个未知的已有项目，或用户要求“梳理代码骨架”、“进行二次开发定位核心代码”时，严格执行以下 4 阶段极速探索纪律。
**【反向约束】：严禁一次性盲目全盘通读文件！必须按骨架大纲逐步收敛。**

---

## Phase 1: 拓扑探测与入口定位 (Topology & Entrypoint)

1. **识别项目形态与技术栈**：
   - 检查根目录配置清单：`package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Makefile`, `Dockerfile` 等。
   - 快速提取核心依赖库（Web 框架、ORM、CLI 库、RPC/消息队列）。

2. **锁定唯一起点 (Entrypoints)**：
   - 寻找程序主启动入口：
     - Python: `main.py`, `app.py`, `manage.py`, `wsgi.py`, `cli.py` 或 `setup.cfg` 中的 entry_points。
     - Node/TS: `src/index.ts`, `src/main.ts`, `src/server.ts`, `app/page.tsx` 等。
     - Go/Rust: `main.go`, `cmd/*/main.go`, `src/main.rs`。
   - **禁止通读入口文件全文**：优先调用 `view_file_outline` 提取顶层函数与注册逻辑，只读取初始化与启动挂载相关的关键切片。

---

## Phase 2: 追踪关键脉络 (Tracer Bullet & Vertical Slice)

以“一个典型用户请求/任务从输入到输出”为线索，打通一条纵向贯穿的调用链（Tracer Bullet）：

1. **路由与请求分发层 (Routing/Dispatch)**：
   - 找到请求/指令如何被解析并路由到具体控制器（Controller/Handler/Action）。
2. **核心业务中枢层 (Core Domain / Service)**：
   - 识别核心调度器或业务服务类。
   - 找出最关键的 1~3 个核心类/函数，理清输入参数与返回值。
3. **数据持久化与外部集成层 (Storage / Adapters)**：
   - 观察数据在哪里落盘（DB/Cache/文件系统/外部 API）。

---

## Phase 3: 寻找二次开发接缝点 (Identify Seams)

为二次开发定位最小侵入性的扩展点：

1. **现有抽象与插件插槽**：
   - 项目中是否存在已定义的基类（Base/Abstract）、协议接口（Interface/Protocol）、插件目录（Plugins/Tools）或中间件栈（Middleware）？
2. **选择修改策略（开闭原则）**：
   - **首选（扩展新模块）**：新功能是否能通过新增一个 Adapter/Handler，仅在配置或路由处注册一行即可生效？
   - **次选（最小侵入补丁）**：若必须修改已有逻辑，锁定最浅的调用点，严禁改动核心底层共有状态。

---

## Phase 4: 输出二次开发全景速查摘要 (Project Blueprint)

在探索收敛后，向用户输出结构清晰的《二次开发全景速查简报》，包含：
1. **项目形态与一句话核心定位**：这个系统具体是做什么的。
2. **核心代码树与职责划分 (20% 最关键文件)**：标明具体路径及行号。
3. **关键数据链路图**：`输入 -> 路由 -> 核心处理 -> 数据存储`。
4. **推荐二次开发接缝点 (Seams)**：如果用户要加新功能，建议从哪个文件、哪个类/函数切入。
