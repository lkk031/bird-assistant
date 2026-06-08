# CLAUDE.md

项目指引（每次会话自动加载，请保持精简）。

## Commands

```bash
poetry run assistant-bird                       # 启动桌面窗口
poetry run assistant-bird --dev                 # 浏览器开发模式（http://localhost:19900）
poetry run ruff check src/ tests/               # Lint
poetry run ruff check --fix src/ tests/         # Auto-fix
poetry run mypy src/                            # Type check
poetry run pytest                               # All tests
poetry run pytest -k "memory" -v                # Single keyword
```

**Desktop env**: 桌面模式需要 GTK WebKit（系统 Python 3.12 + `python3-gi`）。本项目 Poetry 环境已通过符号链接将系统 `gi`/`cairo` 模块暴露给 venv。不要升级/删除这些符号链接。

## Architecture

**Desktop App (pywebview)** — Quart server + native OS window. The server and window run in the same process — Quart in a daemon thread, pywebview in the main thread.

Data flow: frontend POST /chat → SSE streaming → `astream_events(v2)` → Supervisor → sub-agent → SSE events → frontend renders.

| Component | Location | Purpose |
|-----------|----------|---------|
| Window | `desktop/window.py` | pywebview native window + server lifecycle |
| Server | `server/` | Quart HTTP+SSE (routes, session, app factory) |
| Frontend | `desktop/` (index.html, css/, js/) | Chat UI — vanilla HTML/CSS/JS |

### Agents

| Agent | File | Tools |
|-------|------|-------|
| Supervisor | `agents/supervisor.py` | Auto handoff tools |
| General | `agents/general.py` | 0（纯对话/写作/推理） |
| Research | `agents/research.py` | 10 工具 from `tools/registry.py` |
| File Ops | `agents/filesystem.py` | 11 工具（inline `@tool`） |
| Memory | `agents/memory_agent.py` | 4 工具（inline `@tool`） |

State (`graph/state.py`): `AssistantState` — `messages` (auto-reducing), `active_agent`, `user_id`, `memory_context`, `should_memorize`.

Persistence: `AsyncSqliteSaver` → `data/checkpoints.db`（含 aiosqlite `is_alive()` 兼容补丁）。

### Data paths

All data defaults to `~/.local/share/assistant-bird/` (via `app_dir.py` + `platformdirs`). CWD `./data/` takes precedence if it exists (backward compat). `.env` is loaded from CWD first, then app_dir.

## Memory（三层，`memory/memory_manager.py` 编排）

1. **Mem0** — 云端个人事实（API Key 不存在时自动禁用）
2. **Chroma** — 本地向量库（`data/chroma/`，cosine 距离）
3. **SQLite** — 对话历史（`data/conversations.db`，WAL 模式）

Pre-turn 三路并行查询 → `memory_context`；Post-turn 存入 SQLite + Mem0。

## UI（`ui/` + `desktop/`）

| 模块 | 职责 |
|------|------|
| `conversations.py` | 对话元数据 CRUD、thread 映射、标题提取 |
| `desktop/index.html` | 聊天界面 shell |
| `desktop/js/app.js` | 主控逻辑（状态、事件、SSE 回调） |
| `desktop/js/stream.js` | SSE 流式客户端（fetch + ReadableStream） |
| `desktop/js/components.js` | UI 组件构建（消息气泡、工具卡片、对话列表） |

Thread 映射存于 `thread_map.json`，对话元数据存于 `conversations.json`。桌面模式：session 绑定进程生命周期，"新对话" 创建新 thread_id。

## Server API（`server/routes.py`）

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | 发送消息，SSE 流式返回 |
| GET | `/conversations` | 对话列表 |
| POST | `/conversations/new` | 新建对话 |
| POST | `/conversations/switch` | 切换对话 |
| GET | `/messages/<thread_id>` | 获取消息（历史重放） |
| GET | `/export/<thread_id>` | 导出 Markdown |
| GET | `/health` | 健康检查 |

SSE 事件类型：`token`, `agent_switch`, `tool_start`, `tool_end`, `thinking`, `system`, `done`, `error`

## Tools

`tools/registry.py` — ToolRegistry 单例，注册 10 个工具。Research Agent 工具来自 registry 和 `custom_tools/`。

添加工具：`custom_tools/<name>.py` → `@tool` 装饰 → registry 注册 → agent 分配。

工具约定：返回 `str`、捕获所有异常、使用 `get_logger(__name__)` 的 structlog 格式。

## Key conventions

- **语言**: 系统提示词和 UI 消息使用中文
- **配置**: 始终使用 `get_settings()`，禁止硬编码
- **日志**: `get_logger(__name__)` → structlog，禁止 f-string
- **流式**: `astream_events(version="v2")`，处理 `on_chat_model_stream` / `on_tool_start` / `on_tool_end` / `metadata.langgraph_node`
- **单例**: memory / registry / config / session 使用模块级 `get_*()` 模式
- **错误处理**: 区分 `RecursionError` / `TimeoutError` / 速率限制 / 连接错误
- **文件安全**: 沙箱到 `workspace_root`，写/删需确认；Web 工具加超时和 UA
- **Changelog**: 每次功能/Bug 修改必须追加到根 `CHANGELOG.md`

## How to add an agent

1. `agents/new_agent.py` → `create_new_agent(model)` using `create_react_agent`
2. `graph/builder.py` → 加入 `sub_agents` 列表
3. `server/routes.py` → `AGENT_DISPLAY` 添加显示名

## How to add a tool

1. `custom_tools/<name>.py` → `@tool` 装饰的函数
2. `tools/registry.py` → import + `_tools` dict 注册
3. `agents/<agent>.py` → `get_tools([...])` 分配 + 系统提示词说明
