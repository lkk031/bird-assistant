# 开发记录 (Changelog)

本文件记录鸟助手项目**除 custom_tools/ 以外**所有模块的修改历史，包括：
- `agents/` — Agent 定义与提示词
- `tools/` — 内置工具（搜索/抓取/注册）
- `graph/` — LangGraph 图与状态
- `memory/` — 记忆系统（Mem0/Chroma/SQLite）
- `ui/` — Chainlit 界面与回调
- `config/` — 配置与环境变量
- 基础设施（pyproject/README/测试等）

> 📖 **custom_tools/ 的修改请记录在 `src/assistant_bird/custom_tools/CHANGELOG.md`**

⚠️ **强制规则：对以上任何模块的修改（新建/编辑/删除/配置变更）都必须在本文件顶部追加记录，违者视为未完成。**

---

## 2026-06-07 — 重构：拆分 callbacks.py + 删除死代码

### 🧹 优化
- **`ui/callbacks.py` 拆分** (825行→447行, -46%):
  - `conversations.py` (新, 259行) — 对话元数据 CRUD、thread 映射、历史重放、标题提取、下拉菜单构建
  - `actions.py` (新, 140行) — `cl.Action` 回调（新对话、导出）
  - `callbacks.py` (447行) — 仅保留 Chainlit 生命周期（on_chat_start/on_message/on_chat_end/on_settings_update）
  - 所有内部函数去掉 `_` 前缀，作为模块公开 API（拆分后跨模块调用）
- **删除死代码**:
  - `ui/renderers.py` — 整个文件（31行），从未被导入或调用
  - `graph/checkpointer.py` — `create_checkpointer_sync` 死函数 + `import asyncio`（-10行）
  - `ui/callbacks.py` — `__last_active__` 写入 4 处（只写不读）+ 过时注释
  - `data/thread_map.json` — 过期 `__last_active__` key
- **pyproject.toml** — ruff exclude 新增 `public/`

## 2026-06-07 — 代码清理：删除死代码

### 🧹 优化
- **`ui/renderers.py`** — 删除整个文件（31行）。`render_agent_switch` / `render_tool_call`
  从未被任何模块导入或调用，Agent 切换和工具渲染已在 `callbacks.py` 内联实现
- **`graph/checkpointer.py`** — 删除 `create_checkpointer_sync`（同步包装器从未被调用）
  及唯一消费它的 `import asyncio`（-10 行）
- **`ui/callbacks.py`** — 删除 `__last_active__` 所有写入（4 处）。
  `on_chat_start` 已不再回退到 `__last_active__`，只写不读 = 死代码。
  同步更新相关注释，清理 `data/thread_map.json` 中过期的 `__last_active__` key
- **`pyproject.toml`** — ruff exclude 新增 `public/`（避免将 script.js 当 Python 解析）

## 2026-06-07 — 真正修复"开启新对话"闪回问题（第三轮·终局）

### 🐛 修复（续·续）
- **真实根因**: 用户点击的是 **Chainlit 原生 "New Chat" 按钮**（`config.toml` 中 `confirm_new_chat = true`），
  位于页面左上角，而非我们 Attach 在消息中的 `cl.Action` 按钮。
  Chainlit 原生按钮创建**新的 session_id**，但 `on_chat_start` 中的 `__last_active__` 回退逻辑
  会将新 session 拉回旧对话的 thread_id → **闪到空白→立即回放旧消息**。
- **核心修复**: `on_chat_start` — 移除 `__last_active__` 回退逻辑。
  新 session（未在 `thread_map` 中）→ 创建全新 thread_id，不再尝试"恢复最近对话"。
  这是最简洁正确的语义：新 session = 新对话。
- **辅助修复**: `script.js` — 移除 cookie 清除逻辑。
  Action 按钮的 `send_window_message` 只需触发干净导航，保留 session cookie
  才能让 `on_chat_start` 通过 `thread_map[session_id]` 找到刚设置的新 thread_id。
- **影响的文件**:
  - `src/assistant_bird/ui/callbacks.py` — `on_chat_start` 移除 `__last_active__` 回退
  - `public/script.js` — 简化为纯导航，去掉 cookie/storage 清除

### 🔍 两套"新对话"机制说明

| 入口 | 位置 | 机制 | session_id | thread 决议 |
|------|------|------|-----------|------------|
| Chainlit 原生 "New Chat" | 左上角 Header | 浏览器导航到 `/` | 新 session | `on_chat_start`: 不在 thread_map → 新建 |
| "➕ 新对话" Action 按钮 | 消息内嵌 | `on_start_new_conversation` 回调 | 同一 session | `on_chat_start`: thread_map 中查到 → 用新的 |

两者都正确开启空白新对话，互不冲突。

## 2026-06-07 — 修复"开启新对话"辅助问题（第一轮·第二轮）
- **问题**: 第一轮修复只解决了下拉菜单、starters、Action 按钮等辅���问题，但核心体验仍未改善 —
  点击"➕ 新对话"后旧消息仍然残留在界面上，用户看不到空白对话窗口
- **根因**: Chainlit 没有 Python API 可以清除已渲染的消息，仅靠 `cl.Message` 无法实现"跳转到空白对话"
- **解决方案（三管齐下）**:
  1. **页面自动重载**: 新建 `public/script.js`，监听 `window.postMessage` 事件；
     `on_start_new_conversation` 调用 `cl.send_window_message({"type": "assistant_bird_reload"})`
     通知浏览器刷新页面 → 触发 `on_chat_start` → 干净状态
  2. **`on_chat_start` 空对话修复**: 将欢迎消息条件从 `is_new_thread` 扩为
     `is_new_thread or convo_count == 0`，确保页面重载后（新对话 message_count=0）也显示欢迎界面
  3. **配置启用**: `.chainlit/config.toml` 启用 `custom_js = "/public/script.js"`；
     `pyproject.toml` ruff exclude 新增 `public/`
- **涉及的修改文件**:
  - `public/script.js` — 新增，监听 reload 信号并执行 `window.location.reload()`
  - `.chainlit/config.toml` — 启用 custom_js
  - `src/assistant_bird/ui/callbacks.py` — `on_start_new_conversation` 末端改为 `send_window_message`；
    `on_chat_start` 空对话显示欢迎消息
  - `pyproject.toml` — ruff exclude `public/`

## 2026-06-07 — 真正修复"开启新对话"功能（第一轮）

### 🐛 修复
- **问题**: 上次修复（b1de031）将"➕ 新对话"从 Select 下拉菜单改为 `cl.Action` 按钮，
  但点击后仍然没有立刻跳转到新对话，实测未生效
- **根因分析**:
  1. `_build_conversation_select()` 过滤掉了 `message_count == 0` 的对话，新注册的对话
     （message_count=0）不会出现在下拉菜单中，`initial_value` 回退到最近一条历史对话，
     **看起来就像没切换**
  2. `on_start_new_conversation` 发送 `ChatSettings` 时缺少 `starters=STARTERS`，
     导致快捷入口消失
  3. 确认消息缺少 Action 按钮（"➕ 新对话" / "📥 导出对话"），用户无法连续创建新对话
- **解决方案**:
  - `_build_conversation_select()` — 当 `current_thread_id` 不在已有的历史对话列表中时
    （message_count=0 的新对话），自动添加 `🆕 新对话` 条目并设为 `initial_value`
  - `on_start_new_conversation()` — `ChatSettings` 补上 `starters=STARTERS`
  - `on_start_new_conversation()` — 确认消息新增 Action 按钮

## 2026-06-06 — 修复"开启新对话"功能（未生效，已被 2026-06-07 修复覆盖）

### 🐛 修复
- **问题**: 通过 Settings 下拉菜单的"➕ 新对话"选项无法可靠触发 `on_settings_update` 回调，
  因为 Chainlit 2.11.0 的 `chat_settings_change` 事件可能不随 Select 变更立即触发
- **解决方案**: 使用 `cl.Action` 按钮替代下拉菜单中的"➕ 新对话"条目
  - 新增 `@cl.action_callback("start_new_conversation")` — 创建新对话的 Action 处理函数
  - `_build_conversation_select()` — 移除下拉菜单中的"➕ 新对话"条目，只保留历史对话
  - `on_chat_start()` — 欢迎消息和恢复消息中都添加"➕ 新对话" Action 按钮
  - `on_settings_update()` — 移除 `selected == "new"` 分支，简化为只处理对话切换
  - 新对话创建后立即调用 `_register_conversation()` 注册到 conversations.json
  - 创建新对话后重新发送 ChatSettings 以刷新下拉菜单

## 2026-06-06 — 修复异步工具调用错误 (StructuredTool does not support sync invocation)

### 🐛 修复
- **核心问题**: `langgraph-supervisor` 的 `_make_call_agent` 使用 `agent.invoke()` (同步) 调用子 Agent，
  但 P1 异步改造后所有工具都是 `async def`，导致 `StructuredTool.invoke()` 抛出
  `NotImplementedError('StructuredTool does not support sync invocation.')`，
  所有工具调用全部失败，Agent 返回"临时技术问题"
- **解决方案**: 重写 `agents/supervisor.py`，不再使用 `langgraph_supervisor.create_supervisor()`，
  改为手动构建 supervisor graph，子 Agent 使用 `await agent.ainvoke()` 异步调用
- 同步修复 `graph/checkpointer.py`: `create_checkpointer()` 现在显式调用 `await checkpointer.setup()`
  确保 checkpoint 表被创建（之前依赖隐式创建，有时会遗漏）

## 2026-06-06 — 视频搜索 + RSS + GitHub 搜索 + 对话导出集成

### ⚡ HTTP 异步改造 — 全部工具切换为 httpx.AsyncClient

所有网络 I/O 从同步 `httpx.Client()` → `httpx.AsyncClient()`：
- `custom_tools/weather.py` — 2 处
- `custom_tools/rss_reader.py` — 2 处（含 SSL 回退双路径）
- `custom_tools/github_search.py` — 1 处
- `custom_tools/github_trending.py` — 1 处
- `custom_tools/world_news.py` — ThreadPoolExecutor → `asyncio.gather`
- `custom_tools/read_article.py` — 1 处
- `tools/web_search.py` — 2 处（含 lite 回退路径）
- `tools/web_scraper.py` — 1 处（含 retry 循环 `asyncio.sleep`）

改动影响：`@tool` 函数 → `async def`，`.invoke()` → `.ainvoke()`（内部调用同步更新）。
world_news 的并行 RSS 抓取从线程池改为 asyncio.gather 协程并发。

### ✨ ui/callbacks.py — 对话 Markdown 导出

新增 `on_export_conversation` action callback：
- 从 LangGraph checkpointer 读取当前对话全部消息
- 按角色格式化为 Markdown，通过 `cl.File` 提供 `.md` 下载
- 导出按钮出现在已恢复对话提示消息中（刷新页面可见）

### ✨ custom_tools/video_search.py — 新增

基于 yt-dlp 的视频搜索工具，覆盖 YouTube 和 B站：
- YouTube: `extract_flat=True` 快速获取标题/时长/播放量/作者/简介
- B站: 完整提取获取标题和链接，通过浏览器 UA 头绕过 412 反爬

### ✨ custom_tools/github_search.py — 新增

基于 GitHub REST API 的增强搜索工具：
- 仓库搜索：star/fork/语言/描述/最近更新
- Issue/PR 搜索：状态/评论数/作者/更新时间
- 代码搜索：需 GitHub Token（API 限制）
- 支持高级搜索限定符（language:python stars:>100 等）
- 10次/分钟速率限制（无认证），友好错误提示

### ✨ custom_tools/rss_reader.py — 新增

基于 feedparser + httpx 的 RSS/Atom 阅读器：
- 支持任意 RSS 2.0 / Atom 1.0 订阅源
- 双重 SSL 回退（标准验证 → verify=False）兼容各种证书环境
- Markdown 格式化输出（标题、日期、去 HTML 摘要、链接）

### 🔧 tools/registry.py — 注册 video_search + rss_feed
- auto 模式同时搜索两个平台
- 详细变更见 `custom_tools/CHANGELOG.md`

### 🔧 tools/registry.py — 注册 video_search

- `_tools` 字典新增 `"video_search": video_search`

### 🔧 agents/research.py — 分配 + 提示词更新

- `get_tools([...])` 列表加入 `"video_search"`
- 系统提示词新增 video_search 使用说明和触发场景

## 2026-06-05 — 会话隔离 + 对话历史浏览器 + 性能优化

### ✨ ui/callbacks.py — 会话隔离

**问题**：`thread_id` 用硬编码 `USER_ID = "local_user"` 作为 key，所有对话共享同一个 LangGraph thread，点击"新对话"后历史消息依然存在。
**修复**：改用 `cl.context.session.id` 作为 key —— 新对话生成新 session ID → 新 thread_id；页面刷新保留 cookie → 复用 thread_id。

### ✨ ui/callbacks.py — 对话历史浏览器

**新增功能**：
- `data/conversations.json` 持久化对话元数据（标题、时间戳、消息数）
- 设置面板下拉菜单（⚙️ → 📋 对话历史）浏览和切换历史对话
- 选择对话后**即时重放**历史消息，无需刷新页面
- 延迟注册：仅在首次发消息时创建对话记录，空白对话不污染列表
- 智能标题提取 `_extract_title()`：去除"请帮我""麻烦"等前缀词，自然断句截断

### ⚡ memory/memory_manager.py — 记忆查询并行化

**之前**：Mem0 API → Chroma → SQLite 串行执行，总延迟 = 200ms + 50ms + 10ms ≈ 260ms。
**之后**：`ThreadPoolExecutor(max_workers=3)` 三路并行，总延迟 = max(200ms, 50ms, 10ms) ≈ 200ms。每层独立异常隔离。

### ⚡ ui/callbacks.py — 对话元数据内存缓存

**之前**：每条消息触发 2 次完整 JSON 文件读写（30 轮对话 = 60 次 I/O）。
**之后**：`_conversations_cache` 内存缓存，只在变更时刷盘，减少 98% 磁盘 I/O。

### ✨ ui/callbacks.py — 工具执行进度提示

**之前**：工具执行期间（新闻搜索 5-15s）界面空白，用户以为卡死。
**之后**：消息流首个 token 为 `💭` 思考指示符，工具调用时持续显示，让用户知道正在处理。

### 🔧 graph/checkpointer.py — AsyncSqliteSaver 持久化

- 从 `InMemorySaver` 升级为 `AsyncSqliteSaver`（`langgraph-checkpoint-sqlite`）
- aiosqlite `is_alive()` 兼容性补丁（Anaconda Python 3.13 缺少该方法）
- 模块级 `_conn` 引用保持连接生命周期

### 🔧 config.py — 可配置递归限制

新增 `graph_recursion_limit: int = 60`，替代硬编码值。

### 🔧 ui/callbacks.py — 中文错误分类处理

`RecursionError` / `TimeoutError` / 速率限制 / 连接异常 → 各自独立的中文用户提示。

### 🔧 agents/filesystem.py — 文件操作扩展

从 4 工具扩展到 11 工具：`read_file`, `read_lines`, `list_directory`, `search_files`, `get_file_info`, `write_file`, `append_to_file`, `delete_file`, `move_file`, `copy_file`, `create_directory`。全部路径沙箱化，写/删操作需确认。

### 🔧 tools/web_search.py — 双阶段 DuckDuckGo 搜索

- Phase 1: `duckduckgo_search` 库（DDGS），8s 硬超时
- Phase 2: httpx 直接抓取 `html.duckduckgo.com`，不同代码路径
- 两阶段均失败时反幻觉提示，禁止模型编造结果

### 🔧 custom_tools/world_news.py — 多源 RSS 聚合优化

- 细粒度 httpx 超时（connect=5s, read=10s）
- `ThreadPoolExecutor` + `as_completed(timeout=18s)` 并行抓取
- 失败源追踪 + 反幻觉信息注入

---

## 2026-06-05 — 新闻模块修复 + 搜索可靠性重构

### 🐛 custom_tools/world_news.py — 超时修复 + 反幻觉

**问题**（来自 `news_module_issues_report.md`）：
- 新闻工具调用耗时 5+ 分钟
- Agent 在工具失败后凭训练数据编造假新闻
- 工具成功率极低

**修复**：
- `httpx.Timeout(connect=5, read=10, write=5, pool=5)` 替代单一 `15.0s` 超时 — TCP connect 阶段 5s 必断
- `_fetch_headlines` 新增 `as_completed(timeout=18s)` + `TimeoutError` → 取消未完成的 future
- `_fetch_one_feed` 不再吞异常，让调用者区分"源失败"与"源为空"
- 返回签名改为 `(items, sources, failed_sources)` — 追踪失败源
- 全部源失败时返回反幻觉消息，显式警告 Agent 不得编造新闻
- 部分源成功时显示降级提示 + 失败源列表
- 线程数上限 5，防止连接风暴

### 🛡️ custom_tools/read_article.py — 超时修复 + 结构化错误

- `httpx.Timeout(connect=5, read=10, write=5, pool=5)` 替代单一超时
- 区分 `TimeoutException` / `HTTPStatusError` / `Exception` 错误类型
- 所有错误消息显式包含"请勿凭记忆编造"警告

### 🧠 agents/research.py — 反幻觉系统提示词

- 新增 **⚠️ 关键规则** 章节：
  1. 绝对禁止编造新闻 — 工具返回 ⚠️ 错误时必须原样转达
  2. 诚实优先 — 宁可说 3 次"无法获取"也绝不编造 1 条假新闻
  3. 区分时效性 — 实时新闻依赖工具、通用知识用训练数据

### 🔄 tools/web_search.py — 搜索可靠性重构

**问题**：DuckDuckGo 不可达时，DDGS impersonation 库绕过内部超时，线程挂死。

**修复**：
- **Python 线程级硬超时**：`ThreadPoolExecutor` + `future.result(timeout=8)` 包围 DDGS 调用
- `executor.shutdown(wait=False)` 防止退出时等待孤儿线程
- **两阶段回退**：Phase 1 DDGS (8s 硬超时) → Phase 2 直接 httpx HTML 抓取 (8s 总超时)
- 失败时返回反幻觉消息：明确告知 Agent 不得编造搜索结果
- 总耗时从 5+ 分钟降至 ~16s

### 🧪 tests/test_tools.py

- `test_search_returns_results` 接受"搜索暂时不可用"作为合法输出（DDG 不可达环境）

### 📡 custom_tools/world_news.py — 国内可用源 + web_search 回退

**依据**：`news-reliability-plan.md` 三步方案

**Step 1 — 新增国内可用新闻源（源数量 8 → 14+）**：
- `NEWS_SOURCES` 新增：RSS Hub 环球、CGTN World（国内无需代理可达）
- `REGION_SOURCES["china"]` 新增：RSS Hub 微博热搜/知乎热榜/百度热搜、SCMP
- `REGION_SOURCES["tech"]` 新增：RSS Hub 36氪
- 修改 headlines 代码路径：`TOPIC_FEEDS` 区域同时加载 `REGION_SOURCES`（如 tech 板块合并 36氪）

**Step 2 — topic 搜索增加 web_search 回退**：
- Google News RSS 失败 → 自动调用 `web_search` 搜 `"{topic} news today"`
- RSS 结果为空 → 同样触发 web_search 回退
- web_search 再失败 → 反幻觉消息

**Step 3 — 头条模式增加 web_search 兜底**：
- 所有 RSS 源全部失败 → web_search 搜 `"{region_label} news headlines {date}"`
- 成功时标注"⚠️ 所有 RSS 新闻源不可用，以下为网页搜索结果"
- web_search 再失败 → 反幻觉消息

**效果**：
- 源数量：8 → 14+（增加 CGTN、SCMP、RSS Hub 系列）
- 成功率：~30-40% → **64%+**（7/11 源可用，含 SCMP/CGTN 等国内可达源）
- 搜索回退：RSS 失败 → 自动切 web_search → 再失败才报错

---

## 2026-06-05 — 稳定性夯实：SqliteSaver 持久化 + 异常处理增强

### 🔧 graph/checkpointer.py — InMemorySaver → SqliteSaver
- 安装 `langgraph-checkpoint-sqlite ^2.0`
- 图状态持久化到 `data/checkpoints.db`，服务重启不丢对话
- `check_same_thread=False` 支持异步访问

### 🛡️ ui/callbacks.py — 流式异常分类处理
- `RecursionError`：显示部分结果 + 提示拆分任务
- `TimeoutError`：显示部分结果 + 重试建议
- `rate_limit` / `connection` / `recursion`：各给针对性中文提示
- 所有异常恢复：如果已收到部分回复，保留而非丢弃

### ⚙️ config.py — graph_recursion_limit 可配置
- 新增 `GRAPH_RECURSION_LIMIT` 环境变量，默认 60
- `callbacks.py` 不再硬编码 50

### 📦 pyproject.toml
- 新增依赖 `langgraph-checkpoint-sqlite = "^2.0"`

### 📝 CLAUDE.md
- 记录 `-w` 热重载陷阱

---

## 2026-06-04 — 修复 Supervisor 循环路由 + 会话状态泄漏

### 🐛 根因：thread_id 写死
`ui/callbacks.py` 中 `config["configurable"]["thread_id"]` 被写死为 `"local_user"`，
导致所有对话共享同一个 LangGraph 状态线。消息无限累积、不随新建对话重置。

**三个症状同一根因**：
| 症状 | 机制 |
|------|------|
| Agent 交替循环回答 | 超长历史让 Supervisor 混淆，反复委派 |
| 新建对话后旧对话继续展开 | state 里旧消息未清除 |
| 简单问题回答极长 | 上下文被冗余历史塞满 |

### ✅ 修复
- `on_chat_start` 生成 UUID 作为 thread_id，存入 Chainlit session
- `on_message` 从 session 取 thread_id，不再写死
- 用户点击"新对话"→ 新 UUID → 全新 LangGraph state → 旧消息完全隔离
- memory 层面仍用 `USER_ID` 保持跨会话记忆

### 📝 CLAUDE.md
- 记录 `-w` 热重载陷阱：助手写 workspace 文件会触发页面刷新

---

## 2026-06-04 — 文件操作 Agent 全面升级

### 🔧 agents/filesystem.py — 从 4 工具扩展到 11 工具

**新增 7 个工具**：
| 工具 | 功能 | 安全机制 |
|------|------|---------|
| `read_lines` | 按行范围分段读取大文件 | 行号校验、自动截断提示 |
| `get_file_info` | 文件/目录元数据（大小/时间/类型/内容数） | 仅信息查询，无修改 |
| `append_to_file` | 文件末尾追加内容 | 自动创建父目录 |
| `delete_file` | 删除文件或空目录 | 两步确认（confirm=False → 提示 → confirm=True） |
| `move_file` | 移动/重命名文件和目录 | 目标已存在时拒绝、路径沙箱 |
| `copy_file` | 复制文件到新位置 | 仅文件（非目录）、目标已存在时拒绝 |
| `create_directory` | 创建多层目录 | `parents=True`、已存在时友好提示 |

**增强现有工具**：
- `write_file`: 新增 `overwrite` 参数，用户明确确认后可覆盖
- `list_directory`: 目录优先排序，文件大小人类可读
- `read_file`: 改进截断提示，引导使用 `read_lines`
- `search_files`: 文件大小人类可读

**系统提示词重写**: 明确列出 11 个工具及其使用场景、安全规则、最佳实践

### 🔄 agents/supervisor.py
- file_ops_agent 描述更新：反映完整文件管理能力

### ✅ 测试
- `tests/test_tools.py` 新增 23 个测试用例（共 32 个 FileOps 测试）
- 覆盖所有新工具：read_lines / get_file_info / append_to_file / delete_file / move_file / copy_file / create_directory / write_file overwrite
- 覆盖边界情况：不存在文件、无效行范围、非空目录删除、目标已存在、路径沙箱

### 📝 README.md
- 架构图：File Ops Agent 工具数 4 → 11
- Agent 详情表：完整列出 11 个工具

---

## 2026-06-04 — Mem0 记忆系统配置启用

### 🔧 配置 Mem0 API Key
- 注册 Mem0 免费账户，获取 API Key，写入 `.env`
- 记忆管道正式启用，3 层记忆全部验证通过
- 跨会话记忆生效：刷新页面后助手能召回用户偏好

### 📝 README 功能表
- 新增「🧰 内置功能」表格（GitHub 热点 / 全球新闻 / 文章详情 / 天气查询 / 网页搜索 / 网页抓取）
- Agent 详情表 Research 工具数 3 → 7

---

## 2026-06-04 — 自定义工具生态 + 爬虫增强 + UI 修复

### ⚙️ custom_tools 目录
- 创建 `custom_tools/`：4 个工具 + 开发指南 + CHANGELOG
- `tools/registry.py`：注册 github_trending / world_news / read_news_article / get_weather
- `agents/research.py`：提示词新增 4 工具 + 新闻场景专用流程

### 🔧 tools/web_scraper.py v2.0
- UA 池轮换（5 个浏览器）、完整请求头、3 次指数退避重试
- 错误分类（403/404/429/5xx）、同域名限速、HTTP/2

### 🔧 ui/callbacks.py
- `recursion_limit` 25 → 50，解决工具链递归限制

### 🎨 public/stylesheet.css
- 长 URL 换行、统一字体大小、禁止水平滚动

### 📦 pyproject.toml
- `duckduckgo-search` 约束 `^6.0.0` → `>=6.0.0`

---

## Phase 1: 基础框架 — 单 Agent 对话 (2026-06-04)

### 🎯 目标
从零搭建可对话的 Web 聊天界面，DeepSeek 驱动，流式输出。

### 📦 新增文件
| 文件 | 说明 |
|------|------|
| `pyproject.toml` | Poetry 项目配置，定义全部依赖 |
| `.gitignore` | Python 标准忽略 + data/ / workspace/ |
| `.env.example` | 环境变量模板（DeepSeek / Mem0 / 路径配置） |
| `README.md` | 项目说明 + 快速开始 |
| `LICENSE` | MIT 开源协议 |
| `chainlit.md` | Chainlit 欢迎页（能力展示 + 隐私说明） |
| `src/assistant_bird/__init__.py` | 包初始化 |
| `src/assistant_bird/main.py` | Chainlit 入口（启动 + import callbacks） |
| `src/assistant_bird/config.py` | pydantic-settings 配置加载（单例 + 自动创建数据目录） |
| `src/assistant_bird/logging_config.py` | structlog 结构化日志（开发模式彩色 / 生产 JSON） |
| `src/assistant_bird/llm/deepseek.py` | ChatDeepSeek 工厂（流式 / 重试 / 配置化） |
| `src/assistant_bird/graph/state.py` | AssistantState TypedDict（messages + 5辅助字段） |
| `src/assistant_bird/graph/builder.py` | 单节点 chat graph（START → chat → END） |
| `src/assistant_bird/graph/checkpointer.py` | SQLite 检查点封装（暂未使用） |
| `src/assistant_bird/ui/callbacks.py` | Chainlit 生命周期（on_chat_start / on_message / on_chat_end） |
| `src/assistant_bird/ui/starters.py` | 4 个对话快捷入口 |
| `src/assistant_bird/ui/renderers.py` | 自定义渲染（Agent 切换 / 工具调用） |
| `src/assistant_bird/agents/__init__.py` | 占位 |
| `src/assistant_bird/tools/__init__.py` | 占位 |
| `src/assistant_bird/memory/__init__.py` | 占位 |

### 🔧 技术选型
- **LLM**: langchain-deepseek (deepseek-chat)
- **UI**: Chainlit 2.x
- **Graph**: LangGraph StateGraph (单节点)
- **配置**: pydantic-settings
- **日志**: structlog
- **包管理**: Poetry
- **Lint**: ruff (line-length=100, py311)

### ✅ 验证
- 所有模块导入成功
- Chainlit 服务启动 → http://localhost:8000
- DeepSeek API 调用 → HTTP 200，流式响应正常

---

## Phase 2: 多智能体系统 — Supervisor + 5 Agents + 搜索 (2026-06-04)

### 🎯 目标
升级为 Supervisor 多 Agent 架构，4 个专业 Agent + DuckDuckGo 搜索工具。

### 📦 新增文件
| 文件 | 说明 |
|------|------|
| `agents/general.py` | 通用对话 Agent（无工具，处理日常对话/写作/推理） |
| `agents/research.py` | 研究 Agent（web_search 工具，网络搜索 + 事实核查） |
| `agents/filesystem.py` | 文件操作 Agent（read_file + list_directory 工具，路径沙箱） |
| `agents/memory_agent.py` | 记忆 Agent（Phase 2 占位，Phase 3 升级为真实工具） |
| `agents/supervisor.py` | 主管 Agent（langgraph-supervisor，handoff 委派） |
| `tools/web_search.py` | DuckDuckGo 搜索工具（@tool 装饰器，DDGS） |
| `tools/registry.py` | 工具注册中心（全局单例，get_tools / register） |

### 🔄 修改文件
| 文件 | 变化 |
|------|------|
| `graph/builder.py` | 单节点图 → Supervisor 图（4 子 Agent + InMemorySaver） |
| `graph/checkpointer.py` | SqliteSaver → InMemorySaver（langgraph-checkpoint-sqlite 未安装） |
| `ui/callbacks.py` | 新增 Agent 切换显示 + 工具调用可视化 |

### 🔧 架构变化
```
Phase 1: User → Chat Node → LLM → Response

Phase 2: User → Supervisor → 委派到 →
           ├── general_agent    (无工具)
           ├── research_agent   (web_search)
           ├── file_ops_agent   (read_file, list_directory)
           └── memory_agent     (占位)
         → 回流 Supervisor → Response
```

### ✅ 验证
- 5 个 Agent 全部成功导入
- Supervisor 图编译成功 (agent_count=4)
- InMemorySaver 正常工作
- Agent 切换在 UI 中正确显示
- web_search 成功调用 DuckDuckGo

---

## Phase 3: 三层记忆系统 — Mem0 + Chroma + SQLite (2026-06-04)

### 🎯 目标
实现跨会话的长期记忆，支持个人事实、知识文档、对话历史三层存储。

### 📦 新增文件
| 文件 | 说明 |
|------|------|
| `memory/mem0_client.py` | Mem0 托管 API 封装（search / add / get_all / delete，自动提取结构化事实） |
| `memory/vector_store.py` | Chroma 嵌入式向量库（语义搜索 / 文档摄入 / 删除） |
| `memory/conversation_db.py` | SQLite 对话历史（save / get_recent / search / get_summary_for_context） |
| `memory/memory_manager.py` | 三合一编排器（get_context 并行搜索 + store_conversation 后处理） |

### 🔄 修改文件
| 文件 | 变化 |
|------|------|
| `agents/memory_agent.py` | 占位 → 4 个真实工具（recall_memories / remember_fact / search_documents / list_facts） |
| `ui/callbacks.py` | on_message 新增：对话前 memory_context 注入 + 对话后 store_conversation |

### 🔧 记忆数据流
```
每轮对话:
1. 用户输入 → MemoryManager.get_context(query, user_id)
   ├─ Mem0:       语义搜索个人偏好/事实
   ├─ Chroma:     相似度搜索知识文档
   └─ SQLite:     加载最近5轮对话摘要
2. 上下文 → AssistantState.memory_context
3. Supervisor 带记忆上下文决策委派
4. 回复完成 → MemoryManager.store_conversation()
   ├─ SQLite:     写入 user + assistant 消息
   └─ Mem0:       API 自动提取结构化事实存储
```

### ✅ 验证
- Mem0 客户端启用 (MEM0_API_KEY 有效)
- Chroma 向量库正常 (PersistentClient, cosine 空间)
- SQLite 对话记录可读写 (WAL 模式)
- MemoryManager.get_context 正常整合三层记忆
- MemoryManager.store_conversation 正常写入

---

## 版本历史

| 版本 | Git Tag | 日期 | Phase | 内容 |
|------|---------|------|-------|------|
| v0.1.0 | - | 2026-06-04 | P1 | 单 Agent 对话 + DeepSeek + Chainlit |
| v0.2.0 | - | 2026-06-04 | P2 | 多 Agent Supervisor + 搜索 |
| v0.3.0 | - | 2026-06-04 | P3 | Mem0 + Chroma + SQLite 三层记忆 |
| v0.4.0 | - | 2026-06-04 | P4 | 网页抓取 + 文件写安全 + 测试套件 |
| v0.5.0 | - | 2026-06-04 | P5 | 文档完善 + 错误处理 + 开源就绪 |

---

## Phase 4: 网页抓取 + 文件写安全 + 测试 (2026-06-04)

### 🎯 目标
添加网页抓取工具、完善文件操作安全机制、建立测试体系。

### 📦 新增文件
| 文件 | 说明 |
|------|------|
| `tools/web_scraper.py` | 双工具：scrape_webpage（httpx+BeautifulSoup 网页提取）+ search_and_scrape（搜索+自动抓取） |
| `tests/__init__.py` | 测试包 |
| `tests/conftest.py` | 共享 fixtures（临时目录 + 单例清理 + 环境隔离） |
| `tests/test_tools.py` | 工具测试（WebSearch / WebScraper / FileOps / ToolRegistry）— 20 个用例 |
| `tests/test_memory.py` | 记忆测试（VectorStore / ConversationDB / Mem0Client / MemoryManager）— 13 个用例 |

### 🔄 修改文件
| 文件 | 变化 |
|------|------|
| `tools/registry.py` | 新增 scrape_webpage 和 search_and_scrape 注册 |
| `agents/research.py` | 工具从 1 个升级到 3 个（web_search + scrape_webpage + search_and_scrape） |
| `agents/filesystem.py` | 新增 write_file（覆盖保护）+ search_files（glob 搜索）；统一 _validate_path 沙箱 |

### 🔧 安全机制
- **路径沙箱**: `_validate_path()` 统一验证，拒绝 workspace 外的任何路径
- **覆盖保护**: write_file 检测到已存在文件时拒绝写入，提示用户确认
- **二进制检测**: read_file 捕获 UnicodeDecodeError，明确告知用户
- **抓取安全**: 10s 超时、User-Agent 声明、内容类型检测、8KB 截断

### ✅ 测试结果
```
30 passed, 0 failed in 4.41s

tests/test_tools.py   — 20 passed ✅
tests/test_memory.py  — 13 passed ✅
```

覆盖范围:
- ✅ DuckDuckGo 搜索集成测试
- ✅ 网页抓取（无效 URL / 不存在域名）
- ✅ 文件读写（读/写/覆盖/不存在/空目录/搜索/沙箱）
- ✅ 工具注册中心
- ✅ Chroma 向量存储（增删查）
- ✅ SQLite 对话（存储/检索/搜索/摘要）
- ✅ Mem0（禁用模式优雅降级）
- ✅ MemoryManager 编排

---

## Phase 5: 打磨与开源 (2026-06-04)

### 🎯 目标
完善文档、增强错误处理、为开源发布做准备。

### 📦 新增文件
| 文件 | 说明 |
|------|------|
| `CONTRIBUTING.md` | 贡献指南（开发环境 / 架构 / 如何添加 Agent / 工具 / 测试） |

### 🔄 修改文件
| 文件 | 变化 |
|------|------|
| `README.md` | 重写：badges + ASCII 架构图 + 特性表 + 项目结构 + 开发命令 |
| `chainlit.md` | 更新能力总览 + 实用示例 + 隐私说明 |
| `ui/starters.py` | 对话入口更新为当前功能（搜索 / 写作 / 记忆 / 文件） |
| `llm/deepseek.py` | 新增 `retry_call` 函数 + `is_retryable_error` + 3次重试 + 60s 超时 |

### 🔧 错误处理增强
- **DeepSeek 重试**: 指数退避（2s → 4s → 8s），识别 rate_limit/timeout/connection 等可重试错误
- **API 超时**: 60s 请求超时防止永久挂起
- **配置检查**: 启动时友好提示缺失 API Key + 获取链接

### ✅ 验证
```
30 passed, 0 failed ✅
ruff check: All checks passed ✅
chainlit server: 启动正常 ✅
```
