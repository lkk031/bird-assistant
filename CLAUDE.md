# CLAUDE.md

项目指引（每次会话自动加载，请保持精简）。

## Commands

```bash
poetry run chainlit run src/assistant_bird/main.py       # 启动服务器（不加 -w）
poetry run chainlit run src/assistant_bird/main.py -w    # 开发模式（助手运行时勿用）
poetry run ruff check src/ tests/                        # Lint
poetry run ruff check --fix src/ tests/                  # Auto-fix
poetry run mypy src/                                     # Type check
poetry run pytest                                        # All tests
poetry run pytest -k "memory" -v                         # Single keyword
```

## Architecture

**LangGraph Supervisor Pattern** — Supervisor routes to 4 sub-agents, each a `create_react_agent` graph. Supervisor regains control after every sub-agent turn.

Data flow: `on_message` → memory injection → `astream_events(v2)` → Supervisor → sub-agent → response streamed.

| Agent | File | Tools |
|-------|------|-------|
| Supervisor | `agents/supervisor.py` | Auto handoff tools（手写 graph，非 langgraph-supervisor） |
| General | `agents/general.py` | 0（纯对话/写作/推理） |
| Research | `agents/research.py` | 10 工具 from `tools/registry.py` |
| File Ops | `agents/filesystem.py` | 11 工具（inline `@tool`） |
| Memory | `agents/memory_agent.py` | 4 工具（inline `@tool`） |

State (`graph/state.py`): `AssistantState` — `messages` (auto-reducing), `active_agent`, `user_id`, `memory_context`, `should_memorize`.

Persistence: `AsyncSqliteSaver` → `data/checkpoints.db`（含 aiosqlite `is_alive()` 兼容补丁）。

## Memory（三层，`memory/memory_manager.py` 编排）

1. **Mem0** — 云端个人事实（API Key 不存在时自动禁用）
2. **Chroma** — 本地向量库（`data/chroma/`，cosine 距离）
3. **SQLite** — 对话历史（`data/conversations.db`，WAL 模式）

Pre-turn 三路并行查询 → `memory_context`；Post-turn 存入 SQLite + Mem0。

## UI（`ui/`）

| 模块 | 职责 |
|------|------|
| `callbacks.py` | Chainlit 生命周期（on_chat_start/on_message/on_chat_end/on_settings_update） |
| `conversations.py` | 对话元数据 CRUD、thread 映射、历史重放、下拉菜单 |
| `actions.py` | Action 回调（新对话、导出） |
| `starters.py` | 4 个快捷入口 |

Session→Thread 映射存于 `data/thread_map.json`，对话元数据存于 `data/conversations.json`。新 session = 新 thread；同 session（cookie 持久）= 同 thread。

## Tools

`tools/registry.py` — ToolRegistry 单例，注册 10 个工具。Research Agent 工具来自 registry 和 `custom_tools/`。

添加工具：`custom_tools/<name>.py` → `@tool` 装饰 → registry 注册 → agent 分配。详见 `custom_tools/CUSTOM_TOOLS.md`。

工具约定：返回 `str`、捕获所有异常、使用 `get_logger(__name__)` 的 structlog 格式（`logger.info("event", key=value)`，禁用 f-string）。

## Key conventions

- **语言**: 系统提示词和 UI 消息使用中文
- **配置**: 始终使用 `get_settings()`，禁止硬编码
- **日志**: `get_logger(__name__)` → structlog，禁止 f-string
- **流式**: `astream_events(version="v2")`，处理 `on_chat_model_stream` / `on_tool_start` / `on_tool_end` / `metadata.langgraph_node`
- **Chainlit**: 装饰器（`@cl.on_message` 等）在 import 时自动注册，`main.py` 导入 `callbacks` 以触发
- **单例**: memory / registry / config 使用模块级 `get_*()` 模式，`tests/conftest.py` 在测试模块间清理
- **错误处理**: graph 节点捕获异常返回 `AIMessage`；回调区分 `RecursionError` / `TimeoutError` / 速率限制 / 连接错误
- **文件安全**: 沙箱到 `workspace_root`，写/删需确认；Web 工具加超时和 UA
- **Changelog**: 每次功能/Bug 修改必须追加。`custom_tools/` → `custom_tools/CHANGELOG.md`，其余 → 根 `CHANGELOG.md`

## How to add an agent

1. `agents/new_agent.py` → `create_new_agent(model)` using `create_react_agent`
2. `graph/builder.py` → 加入 `sub_agents` 列表
3. `callbacks.py` → `AGENT_DISPLAY` 添加显示名

## How to add a tool

1. `custom_tools/<name>.py` → `@tool` 装饰的函数（参考 `CUSTOM_TOOLS.md` 模板）
2. `tools/registry.py` → import + `_tools` dict 注册
3. `agents/<agent>.py` → `get_tools([...])` 分配 + 系统提示词说明
