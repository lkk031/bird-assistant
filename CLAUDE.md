# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Development
poetry run chainlit run src/assistant_bird/main.py       # Start server (不加 -w，否则助手写 workspace 文件会触发 reload 导致页面刷新)
poetry run chainlit run src/assistant_bird/main.py -w    # 开发模式（仅在纯代码开发时用，助手运行时勿用）
poetry run assistant-bird                                # CLI alias

# Code quality
poetry run ruff check src/                               # Lint
poetry run ruff check --fix src/                         # Auto-fix
poetry run mypy src/                                     # Type check

# Testing
poetry run pytest                                        # All tests
poetry run pytest tests/test_tools/test_web_search.py    # Single test file
poetry run pytest -k "test_name"                         # Single test by name
```

## Architecture

**LangGraph Supervisor Pattern** — single-entry multi-agent orchestration. A supervisor agent routes user messages to specialized sub-agents, each compiled as an independent `create_react_agent` graph with its own tools. The supervisor regains control after every sub-agent turn (not swarm/handoff).

Data flow per turn: `Chainlit on_message` → `app.astream_events(state, config)` → `Supervisor node` → `Sub-agent (with tools)` → back to supervisor → response streamed to UI.

The graph is assembled in `graph/builder.py`. Currently Phase 1 (simple single-node chat). Phase 2 will replace `build_simple_graph()` with a supervisor graph using `langgraph_supervisor.create_supervisor()`.

### State shape (`graph/state.py`)

All graph nodes read/write `AssistantState(TypedDict)`:
- `messages` — `Annotated[Sequence[BaseMessage], add_messages]` (auto-reducing reducer)
- `active_agent` — name of current agent for UI display
- `user_id` — memory scoping key
- `task_description` — what supervisor decided to do
- `memory_context` — combined context from all 3 memory tiers
- `should_memorize` — flag for post-turn memory extraction

### Module boundaries (vibecoding map)

| Module | Job | Depends on | Phase readiness |
|--------|-----|-----------|-----------------|
| `config.py` | Load `.env` via pydantic-settings, singleton via `@lru_cache` | nothing | ✅ Done |
| `llm/deepseek.py` | `create_deepseek_model()` → `ChatDeepSeek` | config | ✅ Done |
| `graph/state.py` | `AssistantState` TypedDict | langgraph | ✅ Done |
| `graph/builder.py` | Graph assembly (Phase 1: simple, Phase 2: supervisor) | state, llm | ⏳ P1 done, P2 pending |
| `graph/checkpointer.py` | `create_checkpointer(path)` → `SqliteSaver` | nothing | ✅ Done, unused until P2 |
| `ui/callbacks.py` | Chainlit `@cl.on_message` etc. | graph, llm | ✅ Done (single-agent) |
| `agents/` | Sub-agent definitions (empty in P1) | tools, graph | 🔜 Phase 2 |
| `tools/` | LangChain `@tool` functions (empty in P1) | nothing | 🔜 Phase 2 |
| `memory/` | Mem0 + Chroma + SQLite (empty in P1) | config | 🔜 Phase 3 |

### How to add a new agent (Phase 2+ pattern)

1. Create `agents/new_agent.py` with `create_new_agent(model, tools) -> CompiledGraph`
2. Define its system prompt and tool assignments
3. Register in `graph/builder.py` supervisor's agent list
4. Chainlit auto-displays agent via `active_agent` state field

### How to add a new tool (Phase 2+ pattern)

1. Write a Python function in `tools/`, decorate with LangChain `@tool`
2. Register in `tools/registry.py`
3. Assign to the relevant agent in its `create_*_agent()` factory

## Key conventions

- **Chinese-first**: system prompts are in Chinese, UI messages are Chinese
- **Config**: never hardcode API keys/paths. Always use `get_settings()` from `config.py`
- **Logging**: use `get_logger(__name__)` from `logging_config.py` (structlog)
- **Streaming**: LLM responses stream via `app.astream_events(..., version="v2")`. Handle `on_chat_model_stream` for tokens, `on_tool_start`/`on_tool_end` for tools
- **Chainlit**: callback hooks (`@cl.on_message`) auto-register on import. `main.py` imports them at module level for this side effect
- **State updates**: graph nodes return partial dicts, LangGraph merges them. Use `add_messages` reducer for `messages` field (no manual append)
- **Error handling**: graph nodes catch exceptions and return user-facing error `AIMessage`. Callbacks wrap `astream_events` in try/except

## Memory architecture (Phase 3 plan)

Three tiers, orchestrated by `memory/memory_manager.py`:
1. **Personal facts** → Mem0 managed API (auto-extracts structured facts from conversation)
2. **Documents** → Chroma embedded vector DB (semantic search over ingested files)
3. **Conversations** → SQLite for history + `SqliteSaver` for LangGraph state persistence

Pre-turn: search all three → inject into `memory_context`. Post-turn: async extract facts → Mem0, log to SQLite.

## Implementation roadmap

See `/home/lkk/.claude/plans/sorted-riding-river.md` for full plan. Phases:
- **Phase 1** ✅ — single-agent chat with DeepSeek + Chainlit
- **Phase 2** 🔜 — supervisor multi-agent + 5 agents + DuckDuckGo search
- **Phase 3** 🔜 — Mem0 + Chroma + SQLite memory system
- **Phase 4** 🔜 — web scraping + file ops + safety
- **Phase 5** 🔜 — tests, docs, open-source polish
