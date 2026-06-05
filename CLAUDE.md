# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Development
poetry run chainlit run src/assistant_bird/main.py       # Start server (不加 -w，否则助手写 workspace 文件会触发 reload 导致页面刷新)
poetry run chainlit run src/assistant_bird/main.py -w    # 开发模式（仅在纯代码开发时用，助手运行时勿用）
poetry run assistant-bird                                # CLI alias

# Code quality
poetry run ruff check src/ tests/                        # Lint
poetry run ruff check --fix src/ tests/                  # Auto-fix
poetry run mypy src/                                     # Type check

# Testing
poetry run pytest                                        # All tests (41 tests)
poetry run pytest -k "memory"                            # Single keyword
poetry run pytest -v                                     # Verbose
poetry run python -c "
from assistant_bird.custom_tools.github_trending import github_trending
print(github_trending.invoke({'language': 'python', 'since': 'daily'}))
"                                                        # Test a tool interactively
```

## Architecture

**LangGraph Supervisor Pattern** — a supervisor agent routes user messages to 4 specialized sub-agents, each compiled as an independent `create_react_agent` graph with its own tools. The supervisor regains control after every sub-agent turn.

Data flow per turn: `Chainlit on_message` → memory context injection → `app.astream_events(state, config, version="v2")` → `Supervisor node` → sub-agent (with tools) → back to supervisor → response streamed to UI.

### State shape (`graph/state.py`)

`AssistantState(TypedDict)`:
- `messages` — `Annotated[Sequence[BaseMessage], add_messages]` (auto-reducing)
- `active_agent` — current agent name for UI display
- `user_id` — memory scoping key
- `task_description` — what supervisor decided to do
- `memory_context` — combined context from all 3 memory tiers (injected pre-turn)
- `should_memorize` — flag for post-turn memory extraction

### Graph assembly (`graph/builder.py`)

`build_assistant_graph(model)` creates 4 sub-agents, an `AsyncSqliteSaver` checkpointer, then wraps them via `langgraph_supervisor.create_supervisor()`. Returns a compiled graph with persistent checkpointing — graph state survives server restarts.

### Checkpointer (`graph/checkpointer.py`)

Uses `AsyncSqliteSaver` from `langgraph-checkpoint-sqlite`. Contains a compatibility patch for `aiosqlite.Connection.is_alive()` (missing in some Python builds, e.g. Anaconda). Module-level `_conn` reference keeps the aiosqlite connection alive.

## Agents

All agents live in `agents/`, each exposes a `create_*_agent(model) -> CompiledStateGraph` factory.

| Agent | File | Tools | Role |
|-------|------|-------|------|
| **Supervisor** | `agents/supervisor.py` | Auto-generated `transfer_to_*` handoff tools | Routes to specialists, synthesizes results |
| **General** | `agents/general.py` | None | Conversation, writing, reasoning, translation |
| **Research** | `agents/research.py` | 7 tools from registry | Web search, scraping, news, weather, GitHub trending |
| **File Ops** | `agents/filesystem.py` | 11 `@tool` functions (inline) | Full filesystem lifecycle, sandboxed to workspace |
| **Memory** | `agents/memory_agent.py` | 4 `@tool` functions (inline) | Long-term memory recall/store, document search |

**Key distinction**: Research agent tools are registered in `tools/registry.py` and imported from `tools/` and `custom_tools/`. File Ops and Memory tools are defined **inline** in their agent modules (not in the registry) because they need direct access to their respective subsystems.

### Supervisor routing logic

`agents/supervisor.py` uses `langgraph_supervisor.create_supervisor()` with `output_mode="last_message"`. The supervisor auto-generates `transfer_to_<agent_name>` tools. System prompt instructs it to route:
- Simple conversation/writing → `general_agent`
- Search/information → `research_agent`
- File operations → `file_ops_agent`
- Memory operations → `memory_agent`

## Tools system

### Tool registry (`tools/registry.py`)

`ToolRegistry` singleton maps tool name → `BaseTool`. Currently registers 7 tools:

| Tool | Source | Description |
|------|--------|-------------|
| `web_search` | `tools/web_search.py` | DuckDuckGo search with fallback |
| `scrape_webpage` | `tools/web_scraper.py` | httpx + BeautifulSoup extraction |
| `search_and_scrape` | `tools/web_scraper.py` | Combined search → scrape pipeline |
| `github_trending` | `custom_tools/github_trending.py` | GitHub trending repos by language/time |
| `world_news` | `custom_tools/world_news.py` | Multi-source RSS news headlines |
| `read_news_article` | `custom_tools/read_article.py` | Look up article links/details by title |
| `get_weather` | `custom_tools/weather.py` | Open-Meteo weather + 7-day forecast |

### custom_tools/ ecosystem

`custom_tools/` is a **user-extensible tools directory** kept separate from built-in `tools/`. Full guide at `src/assistant_bird/custom_tools/CUSTOM_TOOLS.md`. Pattern for adding a tool:

1. Create `<name>.py` in `custom_tools/` with a `@tool`-decorated function
2. Register in `tools/registry.py` (import + add to `_tools` dict)
3. Assign to the appropriate agent in `agents/<agent>.py` (add to `get_tools([...])` + update system prompt)

Tools must follow these conventions (from CUSTOM_TOOLS.md):
- Return `str` (never dict/list — agents can't parse structured data)
- Catch all exceptions, return error strings (tools must never throw)
- Use `get_logger(__name__)` with `logger.info("tool_name: event", key=value)` format (no f-strings)
- Use `@tool` decorator with type-annotated parameters and descriptive docstrings
- Cap numeric parameters with `min()`/`max()` to prevent extreme values from the agent

### File ops tools (defined in `agents/filesystem.py`)

`read_file`, `read_lines`, `list_directory`, `search_files`, `get_file_info`, `write_file`, `append_to_file`, `delete_file`, `move_file`, `copy_file`, `create_directory` — all sandboxed to `get_settings().workspace_root`. Write/delete operations require explicit user confirmation via `ask_user_permission`.

### Memory tools (defined in `agents/memory_agent.py`)

`recall_memories`, `remember_fact`, `search_documents`, `list_facts` — wrap the Mem0 and Chroma subsystems.

## Memory architecture

Three tiers, orchestrated by `memory/memory_manager.py`:

1. **Mem0** (`memory/mem0_client.py`) — managed API for personal facts. `Mem0Client` wraps `mem0.MemoryClient`. Auto-disabled when `MEM0_API_KEY` is not set.
2. **Chroma** (`memory/vector_store.py`) — local embedded vector DB. `VectorStore` wraps `chromadb.PersistentClient`. Collection `user_knowledge`, cosine distance.
3. **SQLite** (`memory/conversation_db.py`) — conversation history. `ConversationDB` table `conversations`, WAL journal mode.

**Pre-turn**: `MemoryManager.get_context(query, user_id)` searches all three tiers, builds a compact context string (facts capped at 1000 chars, docs at 1000 chars, history at 5 turns). Injected into state as `memory_context`.

**Post-turn**: `MemoryManager.store_conversation()` saves to SQLite and (if Mem0 is enabled) extracts facts to Mem0.

All memory modules use module-level singletons (`get_*()` pattern).

## UI layer (`ui/`)

### Lifecycle callbacks (`ui/callbacks.py`)

- **`on_chat_start`**: Creates DeepSeek model, builds graph, maps browser session → `thread_id` (persisted to `data/thread_map.json`), replays history on page refresh, sends welcome message with agent roster, builds conversation switcher + starter suggestions
- **`on_message`**: Injects memory context, streams via `astream_events(v2)`, handles `on_chat_model_stream` (tokens), `on_tool_start`/`on_tool_end` (tool visualization), detects agent switches (displays `[Agent Name]` banners), updates conversation metadata (`data/conversations.json`), stores conversation to memory. Error handling: `RecursionError` (recursion limit), `TimeoutError` (API timeout), general exceptions (rate limit, connection, etc.) — each with user-friendly Chinese messages
- **`on_chat_end`**: Cleanup logging
- **`on_settings_update`**: Conversation switching — "new" creates a fresh `thread_id`, selecting an existing conversation replays its full history via `_replay_messages()`
- **`_replay_messages(app, thread_id)`**: Reads LangGraph state from checkpointer, replays `human`/`ai` messages into the Chainlit UI. Shared by `on_chat_start` (page refresh) and `on_settings_update` (switching)

### Session isolation

Each browser session (Chainlit `session.id`) maps to a `thread_id` (UUID), persisted in `data/thread_map.json`. This ensures:
- "New Chat" → new session → new thread (clean slate)
- Page refresh → same session (cookie) → same thread → history replayed from checkpointer
- Conversation switching → updates the mapping so refresh preserves the switch

Conversation metadata (`data/conversations.json`) tracks title, created/updated timestamps, and message count per thread. Only conversations with messages are shown in the switcher (max 30, sorted by recency).

### Other UI modules

- `ui/starters.py` — 4 Chainlit `Starter` suggestions
- `ui/renderers.py` — `render_agent_switch()` and `render_tool_call()` (custom display formatting)

## Key conventions

- **Chinese-first**: system prompts are in Chinese, UI messages are Chinese
- **Config**: never hardcode API keys/paths. Always use `get_settings()` from `config.py` (pydantic-settings, `@lru_cache` singleton)
- **Logging**: use `get_logger(__name__)` from `logging_config.py` (structlog). Format: `logger.info("event_name", key=value)`. No f-strings in log calls.
- **Streaming**: LLM responses stream via `app.astream_events(..., version="v2")`. Handle `on_chat_model_stream` for tokens, `on_tool_start`/`on_tool_end` for tools, `metadata.langgraph_node` for agent switching
- **Chainlit**: callback hooks (`@cl.on_message`, `@cl.on_chat_start`, etc.) auto-register on import. `main.py` imports them at module level for this side effect
- **State updates**: graph nodes return partial dicts, LangGraph merges them. Use `add_messages` reducer for `messages` field (no manual append)
- **Singletons**: memory modules, tool registry, config — all use module-level `_instance` + `get_*()` pattern. `tests/conftest.py` clears all singleton caches between test modules
- **Error handling**: graph nodes catch exceptions and return user-facing error `AIMessage`. Callbacks wrap `astream_events` in try/except with specific handling for `RecursionError`, `TimeoutError`, rate limits, and connection errors
- **Tool safety**: file ops sandboxed to `workspace_root`, write/delete require confirmation. Web tools use timeouts and User-Agent headers. All tools catch exceptions and return error strings (never throw)
- **Changelog & Commits**: 每次完成一个阶段性的功能修改或 Bug 修复后，必须追加变更记录。格式：日期 + 版本号 + 分类（新增/修复/优化） + 具体说明。登记位置按改动范围区分：
  - `custom_tools/` 目录下的改动 → 登记在 `custom_tools/CHANGELOG.md` 中
  - 其余所有改动 → 登记在项目根目录的 `CHANGELOG.md` 中

## Tests

41 tests across 2 files:
- `tests/test_memory.py` — 12 tests: `TestVectorStore`, `TestConversationDB`, `TestMem0Client`, `TestMemoryManager`
- `tests/test_tools.py` — 29 tests: `TestWebSearch`, `TestWebScraper`, `TestFileOps` (22 tests covering all 11 file ops + path sandbox), `TestToolRegistry`

`tests/conftest.py` provides `setup_test_env` (autouse fixture: sets temp env vars, clears all singletons before/after each test module) and `workspace_dir` fixture.

Tools are tested via `.invoke({"param": value})`, not direct function calls.

## How to add a new agent

1. Create `agents/new_agent.py` with `create_new_agent(model) -> CompiledStateGraph` using `create_react_agent`
2. Define its system prompt and tool assignments
3. Add `create_new_agent(model)` to the `sub_agents` list in `graph/builder.py`
4. The supervisor auto-generates `transfer_to_new_agent` — no manual registration needed
5. Add display name to `AGENT_DISPLAY` dict in `ui/callbacks.py`

## How to add a new tool

1. Create `custom_tools/<name>.py` with a `@tool`-decorated function (see `CUSTOM_TOOLS.md` for template)
2. Register in `tools/registry.py`: import + add to `_tools` dict
3. Assign to the appropriate agent in `agents/<agent>.py`: add to `get_tools([...])` + document in system prompt
4. Test: `poetry run python -c "from ... import ...; print(...invoke({...}))"`
