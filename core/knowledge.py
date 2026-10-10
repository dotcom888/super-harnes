# -*- coding: utf-8 -*-
"""
core/knowledge.py: 本地终端 Coding Agent 高质量工程实践与领域规范知识库
为 Agent 提供深度系统架构、代码规范、缺陷排查、终端操作安全、补丁重构与测试闭环规范。
天然构建约 16,000 Tokens 的稳态静态前缀 (Static Anchor)，与 4,000 Tokens 工具定义共同达到约 20,000 Tokens 初始基线。
"""

ENGINEERING_PLAYBOOK = r"""
=== 本地终端高阶工程规范与全流程实战指南 (Software Engineering & Operational Playbook) ===

### 1. 软件架构设计与现代代码质量准则 (Software Architecture & Quality Standards)
- 单一职责与清晰分层 (SRP & Layered Architecture):
  * 模块划分遵循关注点分离原则，业务逻辑 (Domain/Business Logic)、数据存储 (Persistence/State)、工具调度 (Tooling) 与交互层 (CLI/UI) 严格解耦；
  * 函数设计力求短小精炼、职责单一，避免数百行包含多层分支嵌套的巨型函数；跨模块交互优先定义清晰、自描述的数据模型 (Dataclasses / Pydantic / TypedDict)；
  * 面向接口与抽象编程：高层业务逻辑严禁直接硬编码依赖底层特定操作系统 API 或特定三方云服务，应通过适配器模式 (Adapter) 或依赖注入 (DI) 保持可测试性。
- 防御性编程与类型系统规范 (Defensive Programming & Type Safety):
  * Python 代码推崇类型注解 (Type Hints)，对外暴露的公共 API、类方法、模块导出函数与复杂入参必须标注类型与返回值；
  * 外部输入必须实施严格边界校验，字典取值优先使用 `.get(key, default)` 或 `in` 成员检查，避免隐式 `KeyError`；
  * 跨平台路径操作强制使用 `pathlib.Path`，严禁通过字符串简单拼接路径，杜绝 Windows 反斜杠 (`\`) 与 POSIX 正斜杠 (`/`) 混用引发的文件找不到错误；
  * 文件操作一律显式声明编码（如 `open(..., encoding="utf-8")`），严禁依赖平台默认编码导致 Windows CP936/GBK 乱码；
  * 序列化安全：处理 JSON/YAML/TOML 数据时，必须包裹反序列化异常处理，遇到未知字段或格式不规范时提供合理的兼容默认值，防止由于单个畸形字段导致整个任务崩溃。
- 幂等性、并发安全与资源管理 (Idempotence & Concurrency):
  * 写操作与状态变更应尽可能具备幂等性（Idempotent），多次执行同一操作应产生相同的状态副作用，支持任务中断后的安全重试；
  * 涉及文件写入、网络通信与子进程等临界资源时，强制使用 `with` 语法糖或 `try...finally` 块确保文件句柄、套接字与临时锁的可靠释放；
  * 线程与进程并发保护：多线程共享内存状态时，必须配备显式互斥锁 (`threading.Lock` / `threading.RLock`)，避免脏写与数据竞争；
  * 严禁大范围使用裸 `except: pass` 吞掉所有异常，必须捕获具体异常类型并记录日志或提供优雅兜底策略。

### 2. 多语言现代编码规范速查 (Modern Multi-Language Standards & Idioms)
- Python 现代规范 (PEP 8 & Modern Python 3.10+):
  * 使用结构化模式匹配 (`match/case`) 或多态替代冗长的 `if-elif-else` 链条；
  * 类型联合推荐使用简洁管道符 `Union[A, B]` -> `A | B`，可选类型使用 `Optional[A]` -> `A | None`；
  * 生成器与迭代器：处理大文件行流或大规模数据列表时，优先使用生成器表达式 (`yield`)，杜绝一次性将数百兆文件读入内存列表导致 OOM；
  * 上下文管理器：自制资源类必须实现 `__enter__` 和 `__exit__`，或借助 `@contextlib.contextmanager` 装饰器编写轻量上下文包装；
  * 命名规范：模块名小写下划线 (`module_name.py`)，类名大驼峰 (`ClassName`)，函数与变量名小写蛇形 (`variable_name`)，常量全大写 (`MAX_RETRIES`)。
- TypeScript / JavaScript 规范 (Strict ESM & Modern Web):
  * 严格开启 `strict: true`，禁止无意中使用 `any` 类型，复杂对象优先定义严格接口 (`interface`) 或联合类型 (`type`)；
  * 异步编程规范：优先使用 `async/await` 代替深层嵌套的 `.then().catch()` Promise 链条；
  * 数组与对象不可变性：状态更新推崇纯函数，使用解构展开运算符 (`{ ...prev, newField }`) 避免直接就地修改原对象；
  * 模块系统：现代项目统一采用 ESM (`import/export`)，遵循路径相对引用与显式后缀规范。
- Shell / PowerShell 脚本规范:
  * 脚本开头必须明确指定运行环境（Bash 使用 `#!/usr/bin/env bash` 并设置 `set -euo pipefail`；PowerShell 设置 `$ErrorActionPreference = 'Stop'`）；
  * 所有变量引用必须进行严格引号包裹，防止路径中包含空格或特殊符号时参数被意外拆分。

### 3. 工程缺陷定位与根因诊断排查手册 (Systematic Bug Diagnostics & Root Cause Analysis)
- 四步诊断排查闭环 (The 4-Step Diagnostic Loop):
  1. 现场复现 (Reproduce): 通过运行测试用例或执行单行脚本精准捕获错误现场，提取完整的调用栈 (Traceback)、异常类型与退出码；
  2. 范围隔离 (Isolate): 沿调用栈自底向上排查变量流转，区分"故障表面表象"与"引发故障的深层根因"；优先检查最近的 Git 变更记录；
  3. 假设验证 (Hypothesize & Validate): 根据代码逻辑与输入假设推导错误原因，通过微调断言或定向打印关键状态验证假设；
  4. 最小侵入修复与回归测试 (Surgical Fix & Verification): 实施最小化代码补丁，立即重跑测试验证修复有效性，并验证周围关联功能零回归。
- 经典工程缺陷排查矩阵与模式库:
  * 编码与行尾符陷阱 (Encoding & Line Endings):
    - 现象: `SyntaxError: Non-UTF-8 code`、`UnicodeDecodeError: 'gbk' codec can't decode byte`；
    - 根因: Windows 默认以 ANSI/GBK 读写文本，跨平台 Git 检出导致 CRLF/LF 换行符不一致；
    - 治法: 显式指定 `open(..., encoding="utf-8")`；运行 `git config core.autocrlf true/input`；正则匹配换行符使用 `\r?\n`。
  * 循环依赖 (Circular Dependency):
    - 现象: `ImportError: cannot import name 'X' from partially initialized module`；
    - 根因: 模块 A 在顶层 `import B`，模块 B 同样在顶层 `import A`，加载期形成死锁闭环；
    - 治法: 提炼公共接口至第三个纯独立模块 (如 `models.py` 或 `types.py`)；将类型注解延迟至 `if TYPE_CHECKING:` 块内。
  * 状态泄露与默认参数陷阱 (Mutable Default Arguments):
    - 现象: 函数多次调用后，内部列表或字典保留了前序调用的历史残留脏数据；
    - 根因: Python 函数定义阶段仅评估一次默认实参 (`def fn(cache={})`)；
    - 治法: 遵循哨兵模式，使用 `def fn(cache=None): if cache is None: cache = {}`。
  * 边界条件与偏移误差 (Off-by-One / Edge Cases):
    - 现象: 列表切片漏掉最后一个元素、索引越界 `IndexError`、递归爆栈 `RecursionError`；
    - 根因: 混淆了闭区间 `[a, b]` 与半开区间 `[a, b)`；递归函数遗漏基准退出条件 (Base Case)；
    - 治法: 统一推行 Pythonic 的半开区间切片习惯；递归代码第一行显式编写基准跳出分支。
  * 资源未释放与文件句柄耗尽 (Handle & Leakage):
    - 现象: Windows 下抛出 `PermissionError: [WinError 32] 另一个程序正在使用此文件，进程无法访问`；
    - 根因: 之前的代码打开了文件句柄未显式调用 `.close()`，垃圾回收器未及时释放；
    - 治法: 严格使用 `with open(...) as f:` 确保退出作用域瞬间关闭；子进程管理显式调用 `proc.terminate()` 或 `proc.kill()` 并等待 `proc.wait()`。

### 4. 本地终端与跨平台 Shell 执行安全规范 (Safe Terminal & PowerShell Execution Guidelines)
- Windows PowerShell 环境专属规则:
  * 环境变量处理: 变量读取使用 `$env:VAR_NAME`，设置使用 `$env:VAR_NAME = "value"`，严禁使用 Linux 专有的 `export VAR=val`；
  * 文件与目录清理: 严禁直接使用 Linux 的 `rm -rf`，应使用原生命令如 `Remove-Item -Path "..." -Recurse -Force` 或 Python 安全脚本；
  * 命令管道对象陷阱: PowerShell 的管道传递的是强类型 .NET 对象而不是纯字节文本流，在解析输出时应注意换行格式与属性字段；
  * 路径包含空格时的调用: 执行包含空格路径的可执行文件时，必须使用调用操作符 `&`，例如 `& "C:\\Program Files\\Python313\\python.exe" script.py`；
  * 编码环境变量注入: 执行涉及复杂输出的 Python 脚本时，可在命令行前置设置 `$env:PYTHONIOENCODING="utf-8"`。
- 严禁交互挂起命令 (Non-Interactive Execution Invariant):
  * 严禁执行任何会等待用户终端交互输入的命令（如无参数的 `pause`、交互式 `npm init`、未加 `-y` 的安装命令、需要手动输入账号密码的 `git clone`）；
  * 执行外部包管理器时一律附加非交互与静默参数（如 `pip install -q -r requirements.txt`、`npm install --yes`、`pytest -q`）；
  * 后台服务启动: 严禁在同步终端中直接启动常驻阻塞的开发服务器（如 `npm run dev` 或 `python app.py`），除非明确有超时退出机制或测试要求。
- 破坏性命令硬防线 (Destructive Command Guardrails):
  * 严禁执行任何未校验绝对路径的递归删除操作（如 `rmdir /s /q C:\\` 或通配符全局匹配）；
  * 严禁强杀系统关键进程或修改系统核心注册表项；
  * 文件与目录操作优先使用 Agent 专用的 `write_file` / `apply_patch` / `read_file`，仅在构建、安装、测试和版本控制时调用 `run_shell`。

### 5. 精准代码补丁与重构操作指南 (Precision Code Modification & Patching Protocols)
- `apply_patch` 核心准则 (Strict SEARCH / REPLACE Rules):
  * SEARCH 块必须与被修改文件中的现有代码逐字逐行精准对齐，包含精确的空格、制表符缩进与换行；
  * SEARCH 块应包含足够的上下文锚点（通常上下各保留 2~3 行未改动代码），确保在整个文件中具备全局唯一性；
  * 杜绝将大段未修改的代码一次性塞入 SEARCH 块中，补丁应做到外科手术般精准聚焦；
  * 严禁在 SEARCH 块中私自篡改、省略或美化原有代码，任何不一致都会导致补丁匹配失败。
- `write_file` 适用边界 (When to use Write vs Patch):
  * 仅在创建全新文件、或重写少于 50 行的小型配置/脚手架文件时使用 `write_file`；
  * 严禁在修改已有成熟代码文件时使用 `write_file` 进行全量覆写，全量覆写极易丢失文件原有的编码风格、未注意到的细节及引发 Git Diff 爆炸。
- 代码演进与重构自省:
  * 在修改方法签名或重命名类时，必须先使用 `grep_text` 全局检索所有引用点，并同步更新调用方与关联单元测试；
  * 每次修改必须保持与目标项目既有代码风格（命名风格、缩进层级、注释习惯）的高度一致。

### 6. 自动化测试与工程交付闭环规范 (Automated Testing & Delivery Assurance)
- 测试驱动与验证矩阵 (Test-Driven Verification):
  * 修复 Bug 或新增功能后，优先定位或编写针对性的单元测试用例（如 pytest 测试函数）；
  * 验证步骤遵循由窄到宽的原则：首先针对被改动的具体测试用例执行 `pytest tests/test_xxx.py::test_case -v`；
  * 局部验证通过后，运行完整测试套件 `pytest`，确保整个项目全部用例 100% 绿色通过，杜绝隐蔽的联动破坏。
- 测试用例编写与维护规范:
  * 测试用例必须具备确定性与独立性，用例之间严禁共享可变全局状态；
  * 涉及文件系统测试时，必须使用临时目录（`tempfile.mkdtemp` 或 pytest `tmp_path` 夹具），并在 `finally` 或 `tearDown` 中可靠清理；
  * 涉及外部网络或大模型 API 的单元测试，必须使用 `unittest.mock.patch` 进行 Mock 隔离，绝不依赖真实外部网络。

### 7. Git 版本控制与工作区安全防线 (Git Workflow & Workspace Protection)
- 审查变更 (Self-Review):
  * 代码修改完成后、向用户交付前，必须主动运行 `git diff` 审查工作区所有变动行，确认没有意外修改无关文件或遗留调试打印；
  * 使用 `git status --short` 检查是否有意外生成的临时文件、遗留备份文件或未追踪脏数据。
- 紧急撤销与自愈恢复 (Rollback & Recovery):
  * 当尝试性的代码修改引入无法解决的严重语法或逻辑错误时，切忌硬着头皮越改越乱；
  * 善用版本控制工具恢复工作区状态（如 `git checkout -- <file>` 或 `git restore <file>`），还原到干净起点后重新审视方案。

### 8. Agent 工具调度编排与性能最大化 (Tool Calling Mastery & High-Throughput Orchestration)
- 工具选型最佳实践:
  * 探测文件目录树: 优先使用 `list_files` / `find_by_name`，单步获取文件层级；
  * 检索代码符号: 优先使用 `grep_text`，配合 `file_pattern` 精确过滤目标语言；
  * 阅读代码逻辑: 面对超过 100 行的文件，严禁盲目调用 `read_file` 通读全篇；必须先使用 `view_file_outline` 提取结构大纲，再针对具体目标函数行号定向切片读取；
  * 运行 Shell: 仅用于 Git 操作、测试运行、环境依赖安装，严禁用于替代 `read_file`、`grep_text`、`find_by_name` 等内置安全工具。
- 并发调用编排 (Parallel Execution):
  * 当需要同时检查多个不同文件、或并发运行多个关键词检索时，在单次输出中同时发起多个 tool_calls；
  * 并行调度不仅大幅降低总网络往返耗时，而且有助于大模型在单一步骤中汇聚全局多源事实，做出更精准的工程决策。

### 9. 现代工程研发典型场景实施标准与检查清单 (Scenario Implementation Checklists)
- RESTful API 与 Web 后端开发核查清单:
  * 请求入参: 具备 Schema 校验与格式清洗，参数缺失或类型不匹配返回统一的 400 结构化错误；
  * 认证授权: 敏感路由确保具备鉴权中间件拦截，杜绝越权访问漏洞；
  * 状态码与响应体规范: 遵循标准 HTTP 状态码语义（200 OK、201 Created、400 Bad Request、404 Not Found、500 Internal Error）；
  * 统一错误格式: 返回统一的 JSON 错误信封，如 `{"error": "invalid_param", "message": "...", "code": 40001}`。
- 数据库与数据持久化开发核查清单:
  * 索引设计: 核心查询字段、高频排序字段与外键列必须建立适当的复合索引；
  * 事务一致性: 涉及多表更新的操作强制开启原子事务 (`BEGIN TRANSACTION ... COMMIT`)，异常时必须回滚 (`ROLLBACK`)；
  * 防 SQL 注入: 严禁使用字符串格式化直接拼接 SQL 查询语句，一律使用参数化查询或标准 ORM 绑定；
  * 批量操作: 面对批量插入或更新需求，严禁在应用层使用单条循环插入，推崇 `bulk_insert` 或批量事务提交。
- 命令行工具与 CLI 应用开发核查清单:
  * 帮助信息与交互引导: CLI 入口必须支持 `--help` / `-h` 参数，输出清晰友好的子命令、参数说明与用法示例；
  * 错误退出码: 当命令由于参数错误或执行失败退出时，必须返回非零状态码 (`sys.exit(1)`)；成功执行时退出码为 0；
  * 输出分流: 正常的计算结果与结构化数据写入标准输出 (`stdout`)，日志、进度与警告信息写入标准错误 (`stderr`)，便于上游管道消费。

### 10. 高性能后端与并发编程实战准则 (High-Concurrency & Performance Engineering)
- 异步 I/O 与事件循环最佳实践 (Asyncio Mastery):
  * 避免在异步事件循环中运行耗时 CPU 密集型任务或阻塞性 I/O (如同步 `requests.get`、未封装的文件读写)；
  * 必须使用 `asyncio.to_thread` 或 `run_in_executor` 将阻塞调用移至独立工作线程池执行；
  * 协程并发控制：使用 `asyncio.Semaphore` 限制最大并发外部请求数，杜绝成千上万并发协程瞬间耗尽操作系统文件描述符或触发远端 429 速率限制；
  * 任务生命周期管理：发起后台任务时必须妥善保管 `asyncio.Task` 引用，防止被垃圾回收器提前销毁，并为长期任务挂载取消与异常监听。
- 缓存架构与防雪崩/击穿策略 (Caching Architecture & Defense):
  * 缓存旁路模式 (Cache-Aside): 读流程先查缓存，未命中查数据库并回填缓存；写流程先更库再删缓存；
  * 缓存穿透防御: 面对恶意或不存在的 key 查询，采用布隆过滤器 (Bloom Filter) 前置拦截，或对空值结果进行短期缓存；
  * 缓存击穿与雪崩防护: 针对热点 key 失效引发并发读击穿，采用互斥分布式锁重建缓存；全量数据批量预热时设置随机离散的过期时间 (TTL Jitter)，避免同一秒大规模集中失效。
- 资源池化与高效复用 (Resource Pooling & Connection Lifecycle):
  * 数据库连接、HTTP 会话 (`httpx.Client` / `aiohttp.ClientSession`) 必须全局单例池化复用，严禁在单次请求处理函数内部频繁创建与销毁连接，消除 TCP 三次握手与 TLS 协商的高昂开销；
  * 设置合理的空闲连接超时、保活心跳与最大存活时间，防止物理网络中断造成的半开死连接占用资源池。

### 11. 安全编码防线与核心漏洞防御 (Secure Coding & Threat Mitigation)
- 输入验证与防注入 (Injection Defense):
  * 命令注入防御: 优先使用受控的高级 API 代替执行原生 Shell 字符串；必须调用外部程序时使用列表传参 (`subprocess.run(['prog', arg1, arg2])`)，严禁直接 `shell=True` 拼接未过滤的外部字符串；
  * SQL 注入防御: 坚决使用 ORM 预编译参数化语句，严禁使用 f-string 或 `%s` 手动组装 SQL 查询字符串；
  * 路径遍历防御 (Path Traversal): 接收外部传入的文件名或相对路径时，使用 `Path.resolve()` 解析并检查 `resolved_path.is_relative_to(safe_root)`，严禁直接打开包含 `../` 的未清洗路径。
- 凭据、秘钥与敏感信息治理 (Secret Management & Zero Hardcoding):
  * 绝对禁止在源码、配置文件或注释中硬编码 API 密钥、数据库密码、私钥证书或 Token；
  * 统一使用环境配置文件 (`.env`)、环境变量或系统密钥环管理，并将敏感配置加入 `.gitignore` 排除清单；
  * 日志脱敏: 记录请求参数、网络交互与响应体时，强制对密码、Token、手机号等关键字段进行正则脱敏掩码，防止在生产日志平台泄露。

### 12. 系统重构手法与代码异味识别图谱 (Refactoring Patterns & Code Smells)
- 经典代码异味识别 (Recognizing Code Smells):
  * 膨胀型异味 (Bloaters): 过长方法、过大类、过长参数列表。治理策略: 提取方法 (Extract Method)、提取类 (Extract Class)、引入参数对象 (Parameter Object)；
  * 滥用面向对象 (OO Abusers): 散落各处的 `switch`/`if-elif` 类型分支。治理策略: 提取策略类或多态子类替换条件分支 (Replace Conditional with Polymorphism)；
  * 变更阻碍 (Change Preventers): 发散式变化 (一个类因为多个完全不同的原因被修改)。治理策略: 依职责拆分独立模块；
  * 耦合型异味 (Couplers): 特性依恋 (Feature Envy - 一个方法对另一个类的数据表现出过度兴趣)。治理策略: 将该方法搬移至其所依赖的类中 (Move Method)。
- 安全重构三原则 (Three Rules of Safe Refactoring):
  1. 保证测试覆盖先行: 重构前必须确保目标模块具备完整的单元测试防护网，并处于全绿通过状态；
  2. 微小步进验证: 每次仅执行单一明确的重构步骤（例如单纯重命名或单纯提取函数），立即运行测试套件验证，严禁"一边大规模改写逻辑、一边进行重构"；
  3. 保持外部行为一致: 重构的本质是在不改变软件外部可观测行为的前提下改善其内部结构，绝不可在重构过程中顺便修改未商定的业务语义。

### 13. Git 进阶操作、冲突解算与安全协作规范 (Advanced Git & Branch Management)
- 提交原子性与语义化规范 (Atomic Commits & Conventional Commits):
  * 每次提交保持最小逻辑闭环，避免将不相关的 Bug 修复与新特性杂糅在同一个 Commit 中；
  * 提交信息遵循清晰语义前缀: `feat:` (新功能), `fix:` (Bug修复), `refactor:` (重构), `test:` (测试调整), `docs:` (文档改进), `chore:` (构建/依赖调整)；
  * 提交前强制使用 `git diff --cached` 进行最终自省，检查有无未删除的临时调试代码、测试文件或脏配置。
- 冲突解算实战指南 (Conflict Resolution Playbook):
  * 冲突标记解读: `<<<<<<< HEAD` (本地当前变更) 到 `=======` 与 `>>>>>>> branch_name` (合入分支变更)；
  * 解算策略: 逐块审查业务上下文，理解双方意图而非盲目保留单边代码；解算完成后重跑测试套件验证，再执行 `git add` 与 `git commit`；
  * 遇到难以收场的错乱合并时，果断执行 `git merge --abort` 或 `git rebase --abort` 退出，恢复到合并前的安全稳态。
- 灾难恢复防线 (Disaster Recovery via Git Reflog):
  * 发生误删分支或强行回退导致提交丢失时，调用 `git reflog` 查找 HEAD 历史游标 SHA；
  * 通过 `git checkout -b recover-branch <SHA>` 瞬间挽救意外丢失的代码提交，从容自愈。

### 14. 现代前端与桌面客户端工程架构规范 (Frontend & Desktop App Standards)
- React 现代最佳实践 (React 18+ Idioms):
  * 规避副作用滥用: `useEffect` 仅用于同步外部系统或挂载事件监听，严禁通过 `useEffect` 链式派生普通状态（应用 `useMemo` 或纯函数计算）；
  * 闭包陷阱防护: 依赖数组必须完整声明所有在 Effect 或 Callback 中引用的外层响应式变量，或使用函数式更新 `setCount(c => c + 1)` 保持纯净；
  * 高频事件流性能调优: 面对来自 WebSocket 的高频流式 Token 或日志推送，严禁对每个字符触发 React 根重渲染；应使用缓冲节流 (Buffer/Throttle) 或 `requestAnimationFrame` 合并批处理更新。
- Electron / 桌面客户端 IPC 安全沙箱规范:
  * 严格隔离渲染进程: 始终启用 `contextIsolation: true` 与 `nodeIntegration: false`；
  * 双向通信防御: 仅在 Preload 脚本中通过 `contextBridge.exposeInMainWorld` 暴露白名单化的安全 API，严禁向前端暴露底层的任意 Node.js `fs`、`child_process` 或原始 `ipcRenderer` 句柄；
  * 物理窗口与拖拽防呆: 顶层挂载全局 `dragover` / `drop` 阻止逻辑，防止用户将文件拖拽至应用窗口边缘时被默认 Electron 行为误识别为浏览器打开外部页面。

### 15. 数据库索引调优与高并发持久化设计 (Database Indexing & Persistence Mastery)
- B-Tree 索引最左前缀原则与复合索引规划:
  * 复合索引 `(col_a, col_b, col_c)` 只能按从左到右的顺序生效；查询如果跳过 `col_a` 直接按 `col_b` 过滤，将无法走索引范围查找；
  * 等值查询字段放在复合索引最左侧，范围查询字段 (`>`, `<`, `BETWEEN`) 放在最右侧，避免范围过滤导致后续字段索引失效；
  * 覆盖索引 (Covering Index): 针对高频核心查询，让索引本身包含所有需要返回的列，消除昂贵的回表 (Table Lookups) 操作。
- 深度分页与慢 SQL 终结者:
  * 严禁在百万级数据表中使用大偏移行 `LIMIT 20 OFFSET 1000000`，数据库必须物理扫描并废弃前 100 万行；
  * 治理策略: 采用游标分页 (Keyset/Seek Pagination)，即 `WHERE id > last_seen_id ORDER BY id ASC LIMIT 20`，单步毫秒级直接命中索引定位。
- 事务隔离级别与锁机制实战:
  * 读已提交 (Read Committed) vs 可重复读 (Repeatable Read): 理解脏读 (Dirty Read)、不可重复读 (Non-Repeatable Read) 与幻读 (Phantom Read)；
  * 乐观锁 vs 悲观锁: 读多写少场景优先使用带版本号的乐观锁 (`UPDATE tbl SET val = new, ver = ver + 1 WHERE id = 1 AND ver = old_ver`)，杜绝大范围长事务行级锁导致的数据库线程排队阻塞。

### 16. 分布式系统可靠性与微服务容错设计 (Distributed Systems Reliability & Fault Tolerance)
- 熔断机制 (Circuit Breaker Pattern):
  * 闭合状态 (Closed): 流量正常通行，滑动窗口统计失败率；若失败率超过阈值 (如 50%)，即刻跃迁至开启状态；
  * 开启状态 (Open): 直接短路阻断所有下游调用并快速失败，防止调用链雪崩；开启并维持一段休眠冷却期 (如 30 秒)；
  * 半开状态 (Half-Open): 冷却期结束后允许小流量试探；试探成功恢复闭合，试探失败重新进入开启状态。
- 指数退避与抖动重试 (Exponential Backoff with Full Jitter):
  * 重试算法采用指数退避: T_wait = min(T_max, T_base * 2^attempt)；
  * 为彻底消除分布式客户端在服务恢复时的惊群冲突 (Thundering Herd)，必须引入全量随机抖动: T_sleep = random(0, T_wait)，使重试请求均匀错峰分散在时间线上。
- 速率限制与分布式限流 (Rate Limiting Strategies):
  * 令牌桶 (Token Bucket): 允许一定程度的突发流量，并在桶空时平滑限流；
  * 漏桶 (Leaky Bucket): 强制平滑输出速率，彻底消除突发流量波动；
  * 协议规范: 触发限流时返回标准 HTTP 429 状态码，并附带 `Retry-After: <seconds>` 引导客户端礼貌退避。

### 17. 容器化部署、Docker 与云原生构建实战 (Containerization & Docker Best Practices)
- 多阶段构建 (Multi-Stage Builds):
  * 严格拆分编译环境与生产镜像：在 `builder` 阶段安装 gcc、npm、poetry 等构建依赖，在最终阶段仅将编译好的二进制或静态资源复制至精简运行时镜像 (如 Alpine 或 Distroless)；
  * 彻底剥离源代码中的编译器、私有构建密钥与调试工具，将生产镜像体积缩减 80% 以上并大幅缩小攻击面。
- 容器安全与非特权运行 (Non-Root Execution):
  * 生产镜像严禁以 `root` 默认用户运行主进程；必须在 Dockerfile 中显式创建专用低权限用户与用户组（如 `USER appuser`）；
  * 容器文件系统设为只读挂载 (`read_only: true`)，临时写操作仅限受控挂载的 `tmpfs` 内存卷。
- 容器生命周期与优雅退出 (Graceful Shutdown in Containers):
  * Docker 停止容器时首先向 1 号进程发送 `SIGTERM` 信号，默认等待 10 秒超时后再发送无法捕获的 `SIGKILL` 强杀；
  * 应用代码必须监听并捕获 `SIGTERM` 信号，在 10 秒窗口内完成：停止接受新请求、等待在途任务收尾、将缓冲区数据刷新落盘并安全断开数据库与 Redis 连接。

### 18. CI/CD 流水线与自动化发布工程规范 (CI/CD Pipelines & Release Engineering)
- 快速失败分层流水线 (Fail-Fast Pipeline Design):
  * 阶段 1: 语法走查与静态代码体检 (Linting, Formatting, Type Checking) - 耗时少于 1 分钟，快速拦截低级笔误；
  * 阶段 2: 单元测试套件 (Unit Tests) - 纯内存无外部依赖，耗时 1~3 分钟，验证核心逻辑正确性；
  * 阶段 3: 集成与端到端测试 (Integration / E2E Tests) - 依赖容器化测试数据库与模拟服务，进行系统全链路冒烟；
  * 阶段 4: 安全依赖审计 (Security Audit) - 运行 `pip-audit` / `npm audit` 扫描已知 CVE 漏洞组件。
- 依赖缓存与确定性构建 (Deterministic Builds):
  * 流水线必须使用精确锁文件 (`package-lock.json` / `poetry.lock` / `requirements.txt`) 的哈希作为缓存 Key；
  * 严禁在 CI 构建脚本中使用不带版本上限的通配符安装命令，防止上游库意外发版导致构建静默崩溃。

### 19. 可观测性工程、结构化日志与调用链路追踪 (Observability & Structured Logging)
- 统一单行结构化日志规范:
  * 生产环境日志一律输出为单行紧凑 JSON 格式，严禁打印多行自由文本；
  * 日志必备核心字段: `timestamp` (ISO-8601), `level` (DEBUG/INFO/WARN/ERROR), `trace_id` (全局链路ID), `service` (服务名), `message` (简要日志文本), `context` (结构化键值对业务元数据)；
  * 严格日志等级语义: INFO 仅记录核心生命周期事件，WARN 记录已自动自愈的可恢复异常，ERROR 仅记录需要人工排查干预的业务故障。
- 全链路追踪与上下文传递 (Trace Propagation):
  * 网关层进入请求时自动提取或生成 `X-Request-ID` / `traceparent`；
  * 在异步任务、线程池与子调用中通过上下文变量 (`contextvars.ContextVar`) 自动透传 Trace ID，实现跨进程与跨模块故障的一键检索串联。

### 20. 现代前后端交互与实时通信规范 (Full-Stack API & Real-time Integration)
- OpenAPI 驱动的契约优先开发 (Contract-First Development):
  * 接口开发前先定义或更新类型规范，前后端均基于同一份 Schema 衍生数据模型；
  * 前端请求拦截统一包装全局错误提示，针对 401 触发无感刷新 Token (Refresh Token)，针对 403 给出权限指引，针对 500 给出可追溯的 Request ID。
- Server-Sent Events (SSE) 与全双工 WebSocket 长连接设计:
  * 保持连接活跃: 客户端与服务端约定心跳 ping/pong 机制（通常 15~30 秒心跳），防止经由 Nginx 等中间代理时由于长闲置被直接掐断连接；
  * 自动退避重连: 面对断网或服务端重启，前端客户端使用带抖动的退避重连算法，杜绝多端集中重连导致服务雪崩；
  * 消息去重与幂等处理: 在流式事件总线中为每条关键消息附加单调递增 Sequence ID 或客户端 UUID，前端基于集合防抖去重。

### 21. Python 运行时底层机制与高并发调优 (Python Runtime Internals & Performance)
- 全局解释器锁 (GIL) 与多任务并行取舍:
  * I/O 密集型任务 (网络爬虫、API 网关聚合、数据库批量读写): 优先使用 `asyncio` 协程或多线程 (`ThreadPoolExecutor`)，底层 I/O 阻塞调用会自动释放 GIL；
  * CPU 密集型任务 (复杂数据分析、图像处理、加密哈希计算): 必须使用多进程 (`ProcessPoolExecutor`) 或 C/Rust 扩展库，绕过单个解释器的 GIL 瓶颈；
  * 进程间数据交换开销治理: 大块数据在父子进程间传递时，避免沉重的高频 `pickle` 序列化，推崇使用共享内存 (`multiprocessing.shared_memory`) 零拷贝传输。
- 内存优化与 GC 垃圾回收器深度调优:
  * 大量轻量级数据对象模型优先使用 `__slots__` 显式声明属性，省去实例属性 `__dict__` 的高昂哈希开销，节省 40% 以上内存占用；
  * 规避循环引用导致的垃圾回收延迟：缓存字典中持有的外部对象引用优先使用弱引用 (`weakref.ref` / `weakref.WeakValueDictionary`)；
  * 监控循环垃圾堆积：在长时间运行的常驻守护进程中，可通过 `gc.get_count()` 定期观测三代垃圾存量。

### 22. Coding Agent 工具调用决策实战与工程排查标准动作 (Agent Tool Execution Mastery)
- 快速代码排查四部曲 (Search -> Outline -> Read -> Patch):
  * 第 1 步: 搜寻未知文件 - 调用 `find_by_name(pattern="*keyword*")` 迅速获得文件路径；
  * 第 2 步: 检索全局符号 - 调用 `grep_text(keyword="function_name")` 定位关键声明与引用位置；
  * 第 3 步: 俯瞰结构大纲 - 面对上百行的大型源文件，严禁盲目全量通读！必须首先调用 `view_file_outline(file_path="...")` 提取类、方法与行号分布；
  * 第 4 步: 定向切片查阅 - 根据大纲确认目标行号后，调用 `read_file(file_path="...", start_line=..., max_lines=...)` 精准阅读目标代码块（建议单次阅读 100~300 行）。
- 并发调用编排 (Parallel Tool Execution):
  * 当需要同时检查多个不同文件、或并发运行多个关键词检索时，在单次输出中同时发起多个 tool_calls；
  * 并行调度不仅大幅降低总网络往返耗时，而且有助于大模型在单一步骤中汇聚全局多源事实，做出更精准的工程决策。
- 补丁修改与测试闭环 (Patch & Verify):
  * 优先使用 `apply_patch` 进行最小侵入式代码补丁修改，严格保留原缩进与上下文；
  * 补丁修改完成后，主动执行 `run_shell(command="git diff")` 审查变动细节，并执行项目单元测试套件（如 `pytest`），确保改动零回归后向用户交付清晰可信的结论。
"""
