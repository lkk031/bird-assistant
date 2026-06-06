"""Chainlit lifecycle callbacks for the assistant."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import chainlit as cl
from chainlit.input_widget import Select
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from assistant_bird.config import get_settings
from assistant_bird.graph.builder import build_assistant_graph
from assistant_bird.llm.deepseek import create_deepseek_model
from assistant_bird.logging_config import get_logger
from assistant_bird.memory.context_manager import check_and_manage_context
from assistant_bird.memory.memory_manager import get_memory_manager
from assistant_bird.ui.starters import STARTERS

logger = get_logger(__name__)

USER_ID = "local_user"
THREAD_MAP_FILE = Path("data/thread_map.json")

AGENT_DISPLAY = {
    "supervisor": "🧠 主管",
    "general_agent": "💬 通用助手",
    "research_agent": "🔍 研究员",
    "file_ops_agent": "📁 文件操作",
    "memory_agent": "💾 记忆管理",
}


def _load_thread_map() -> dict[str, str]:
    """Load the user_id → thread_id mapping from disk."""
    try:
        if THREAD_MAP_FILE.exists():
            return json.loads(THREAD_MAP_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_thread_map(data: dict[str, str]) -> None:
    """Save the user_id → thread_id mapping to disk."""
    THREAD_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    THREAD_MAP_FILE.write_text(json.dumps(data))


# ── Conversation metadata index ──────────────────────────────────────────
# Persists metadata for every conversation so users can browse and switch
# between past conversations. Separate from thread_map (which handles
# session→thread routing and is session-scoped).

CONVERSATIONS_FILE = Path("data/conversations.json")

# In-memory cache to avoid disk I/O on every message.
# Cache is warmed on first load and flushed to disk on every save
# (which only happens when metadata actually changes).
_conversations_cache: dict[str, dict] | None = None


def _load_conversations() -> dict[str, dict]:
    """Load conversation index from cache or disk."""
    global _conversations_cache
    if _conversations_cache is not None:
        return _conversations_cache
    try:
        if CONVERSATIONS_FILE.exists():
            _conversations_cache = json.loads(CONVERSATIONS_FILE.read_text())
            return _conversations_cache
    except Exception:
        pass
    _conversations_cache = {}
    return _conversations_cache


def _save_conversations(data: dict[str, dict]) -> None:
    """Save conversation index to disk and update cache."""
    global _conversations_cache
    _conversations_cache = data
    CONVERSATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONVERSATIONS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _register_conversation(thread_id: str, title: str = "") -> None:
    """Add a new conversation to the metadata index (only called on first message)."""
    conversations = _load_conversations()
    now = datetime.now(UTC).isoformat()
    conversations[thread_id] = {
        "title": title or "未命名",
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    }
    _save_conversations(conversations)


def _ensure_conversation_exists(thread_id: str) -> None:
    """Lazy-register a conversation if it doesn't exist yet."""
    conversations = _load_conversations()
    if thread_id not in conversations:
        _register_conversation(thread_id)


def _update_conversation(
    thread_id: str,
    *,
    title: str | None = None,
    increment_messages: bool = False,
) -> None:
    """Update a conversation's metadata (title, count, timestamp).

    Auto-registers the conversation if it doesn't exist yet (lazy creation
    on first message), so blank/unused conversations are never persisted.
    """
    _ensure_conversation_exists(thread_id)
    conversations = _load_conversations()
    now = datetime.now(UTC).isoformat()
    conversations[thread_id]["updated_at"] = now
    if title:
        conversations[thread_id]["title"] = title
    if increment_messages:
        conversations[thread_id]["message_count"] += 1
    _save_conversations(conversations)


async def _replay_messages(app, thread_id: str) -> int:
    """Replay conversation history from LangGraph state into the Chainlit UI.

    Returns the number of messages replayed (0 if thread is empty or missing).
    Used both by on_chat_start (page refresh) and on_settings_update (switching).
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = await app.aget_state(config)
        if not state or not state.values:
            return 0

        messages = state.values.get("messages", [])
        if not messages:
            return 0

        logger.info(
            "_replay_messages: replaying history",
            thread_id=thread_id,
            message_count=len(messages),
        )
        for msg in messages:
            if hasattr(msg, "type"):
                role = msg.type
                content = msg.content
            elif isinstance(msg, dict):
                role = msg.get("type", "")
                content = msg.get("content", "")
            else:
                continue

            if not content:
                continue

            if role in ("human", "user"):
                await cl.Message(content=str(content), author="You").send()
            elif role in ("ai", "assistant"):
                await cl.Message(content=str(content)).send()

        return len(messages)
    except Exception as e:
        logger.warning("_replay_messages: replay failed", error=str(e))
        return 0


def _extract_title(user_input: str) -> str:
    """Extract a meaningful conversation title from the first user message.

    Always returns a non-empty string — uses the raw message as fallback.
    """
    import re

    raw = user_input.strip()
    if not raw:
        return "对话"

    # Remove common prefixes / noise words
    noise_prefixes = [
        "请帮我", "帮我", "请", "我想让你", "能不能",
        "你可以", "你可以帮我", "麻烦你", "麻烦",
    ]
    for prefix in noise_prefixes:
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break

    raw = raw.lstrip("，,。. ")

    # Truncate to a reasonable title length, breaking at natural boundaries
    if len(raw) > 30:
        truncated = raw[:30]
        match = re.search(r"[，,。.!！?？\s][^，,。.!！?？\s]*$", truncated)
        if match and match.start() > 10:
            raw = truncated[:match.start()]
        else:
            raw = truncated

    return raw.strip() or user_input.strip()[:30]


def _build_conversation_select(current_thread_id: str) -> list:
    """Build a ChatSettings Select widget for conversation switching.

    Returns a list with one Select element so it can be spread into
    ChatSettings(...) alongside other settings.
    """
    conversations = _load_conversations()
    sorted_convos = sorted(
        conversations.items(),
        key=lambda kv: kv[1].get("updated_at", ""),
        reverse=True,
    )

    items: dict[str, str] = {}
    items["➕ 新对话"] = "new"

    # Show all conversations with messages, including archived ones.
    active_convos = [
        (tid, meta) for tid, meta in sorted_convos
        if meta.get("message_count", 0) > 0
    ]

    for tid, meta in active_convos[:30]:
        title = meta.get("title", "未命名")
        updated = meta.get("updated_at", "")[:10]
        count = meta.get("message_count", 0)
        prefix = "📦 " if meta.get("archived") else ""
        # Show fork relationships
        continued_in = meta.get("continued_in", "")
        continued_from = meta.get("continued_from", "")
        if continued_in:
            suffix = " → 续"
        elif continued_from:
            suffix = " ← 续前"
        else:
            suffix = ""
        label = f"{prefix}{updated} · {title} ({count}条){suffix}"
        items[label] = tid

    if len(items) == 1:
        items["(暂无历史对话)"] = "__none__"

    # initial_value must match a *value* (right side) in the items dict
    # Find the label whose value matches current_thread_id
    initial = None
    for label, value in items.items():
        if value == current_thread_id:
            initial = value
            break
    if initial is None:
        initial = "new"

    return [
        Select(
            id="conversation_switch",
            label="📋 对话历史",
            items=items,
            initial_value=initial,
            description="选择历史对话或创建新对话",
        )
    ]


@cl.action_callback("export_current_conversation")
async def on_export_conversation(action: cl.Action) -> None:
    """Export the current conversation as a downloadable Markdown file."""
    thread_id = cl.user_session.get("thread_id")
    app = cl.user_session.get("app")

    if not thread_id or not app:
        await cl.Message(content="⚠️ 无法导出：对话尚未初始化。").send()
        return

    app = cast(CompiledStateGraph, app)
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = await app.aget_state(config)
    except Exception as e:
        logger.error("export: failed to load state", error=str(e))
        await cl.Message(content="⚠️ 加载对话失败，请稍后重试。").send()
        return

    if not state or not state.values:
        await cl.Message(content="⚠️ 当前对话无内容可导出。").send()
        return

    messages = state.values.get("messages", [])
    if not messages:
        await cl.Message(content="⚠️ 当前对话无内容可导出。").send()
        return

    # Build Markdown
    conversations = _load_conversations()
    convo = conversations.get(thread_id, {})
    title = convo.get("title", "对话导出")
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")

    lines = [
        f"# {title}",
        "",
        f"> 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
        f"共 {len(messages)} 条消息  |  "
        f"thread: {thread_id[:8]}",
        "",
        "---",
        "",
    ]

    for msg in messages:
        role = getattr(msg, "type", "")
        content = str(getattr(msg, "content", ""))

        if role in ("human", "user"):
            lines.append("### 🧑 用户")
        elif role in ("ai", "assistant"):
            lines.append("### 🤖 鸟助手")
        elif role == "tool":
            tool_name = getattr(msg, "name", "")
            label = f"工具: {tool_name}" if tool_name else "工具"
            lines.append(f"### 🔧 {label}")
        elif role == "system":
            lines.append("### ⚙️ 系统")
        else:
            lines.append(f"### {role}")

        lines.append("")
        lines.append(content.strip())
        lines.append("")

    markdown = "\n".join(lines)
    filename = f"conversation-{date_str}-{thread_id[:8]}.md"

    await cl.Message(
        content="📥 对话已导出",
        elements=[
            cl.File(
                name=filename,
                content=markdown.encode("utf-8"),
                display="inline",
                mime="text/markdown",
            )
        ],
    ).send()

    logger.info(
        "export: conversation exported",
        thread_id=thread_id,
        message_count=len(messages),
        file_size=len(markdown),
    )


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialize the assistant when a new chat session starts."""
    # Get or create a thread_id for this browser session.
    # Key = Chainlit session ID. However, without auth, Chainlit may
    # generate a new session.id on refresh. We use __last_active__
    # as a fallback to preserve the active conversation across refreshes.
    session_id = cl.context.session.id
    thread_map = _load_thread_map()
    is_new_thread = False

    if session_id in thread_map:
        # Exact match: same session (cookie preserved across refresh)
        thread_id = thread_map[session_id]
        logger.info(
            "on_chat_start: reusing thread_id",
            session_id=session_id,
            thread_id=thread_id,
        )
    else:
        # Session not found — could be first visit, "New Chat" button,
        # or refresh without cookie persistence.
        last_active = thread_map.get("__last_active__")
        if last_active:
            # Resume the most recently active conversation (handles refresh)
            thread_id = last_active
        else:
            # Truly first visit — create a new conversation
            thread_id = str(uuid.uuid4())
            is_new_thread = True

        # Map this session to the resolved thread for future lookups
        thread_map[session_id] = thread_id
        thread_map["__last_active__"] = thread_id
        _save_thread_map(thread_map)
        logger.info(
            "on_chat_start: resolved thread_id",
            session_id=session_id,
            thread_id=thread_id,
            is_new_thread=is_new_thread,
            has_last_active=bool(last_active),
        )

    cl.user_session.set("thread_id", thread_id)

    try:
        model = create_deepseek_model()
    except ValueError as e:
        logger.error("on_chat_start: failed to create model", error=str(e))
        await cl.Message(
            content=f"⚠️ 配置错误：{str(e)}\n\n请确保 `.env` 文件中已正确配置 API Key。"
        ).send()
        return

    cl.user_session.set("model", model)  # Store for context summarization
    app = await build_assistant_graph(model)
    cl.user_session.set("app", app)

    # If reusing an existing thread, replay conversation history in the UI.
    if not is_new_thread:
        await _replay_messages(app, thread_id)

    # Build conversation title for display
    conversations = _load_conversations()
    convo_meta = conversations.get(thread_id, {})
    convo_title = convo_meta.get("title", "新对话")
    convo_count = convo_meta.get("message_count", 0)

    # Only show welcome message for new threads
    if is_new_thread:
        await cl.Message(
            content=(
                "🐦 **鸟助手 (Assistant-Bird) 已就绪！**\n\n"
                "我的团队包括：\n"
                "🧠 **主管 Agent** — 理解意图，调度专家\n"
                "💬 **通用 Agent** — 对话、写作、推理\n"
                "🔍 **研究 Agent** — 网络搜索、信息获取\n"
                "📁 **文件 Agent** — 文件读写、目录浏览\n"
                "💾 **记忆 Agent** — 长期记忆、知识管理\n\n"
                "有什么我可以帮你的吗？"
            )
        ).send()
    elif convo_count > 0:
        await cl.Message(
            content=(
                f"📋 **已恢复对话**: {convo_title}（{convo_count} 条消息）\n\n"
                "点击右上角 ⚙️ 可浏览和切换历史对话。"
            ),
            actions=[cl.Action(
                name="export_current_conversation",
                label="📥 导出对话",
                description="导出当前对话为 Markdown 文件",
            )],
        ).send()

    # Build settings with conversation switcher + starters
    select_widgets = _build_conversation_select(thread_id)
    await cl.ChatSettings(
        inputs=select_widgets,
        starters=STARTERS,
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle incoming user messages and stream the assistant's response."""
    app = cl.user_session.get("app")
    if app is None:
        await cl.Message(content="⚠️ 助手尚未初始化，请刷新页面重试。").send()
        return

    app = cast(CompiledStateGraph, app)
    user_input = message.content

    # Use session-scoped thread_id so each conversation is independent.
    # Falls back to a new UUID if somehow missing (shouldn't happen).
    thread_id = cl.user_session.get("thread_id")
    if thread_id is None:
        thread_id = str(uuid.uuid4())
        cl.user_session.set("thread_id", thread_id)

    # Phase 3: Inject memory context (keyed by USER_ID for cross-session memory)
    memory_mgr = get_memory_manager()
    memory_context = memory_mgr.get_context(user_input, USER_ID)

    # ── Context window management ──────────────────────────────────────
    # Check if the conversation has grown too long. If so, summarize older
    # messages and fork to a new thread transparently.
    settings = get_settings()
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.graph_recursion_limit,
    }

    state_override = False  # Set to True if fork builds its own state
    model = cl.user_session.get("model")
    if model is not None:
        try:
            existing_state = await app.aget_state(config)
            existing_messages: list = []
            if existing_state and existing_state.values:
                existing_messages = list(existing_state.values.get("messages", []))

            seed_messages, summary, did_fork = await check_and_manage_context(
                model, existing_messages,
            )

            if did_fork:
                new_thread_id = str(uuid.uuid4())
                # Update thread mapping (session → new thread)
                thread_map = _load_thread_map()
                old_thread_id = thread_id
                thread_map[cl.context.session.id] = new_thread_id
                thread_map["__last_active__"] = new_thread_id
                _save_thread_map(thread_map)
                cl.user_session.set("thread_id", new_thread_id)
                thread_id = new_thread_id

                # Update conversation metadata: archive old, create new
                conversations = _load_conversations()
                old_title = conversations.get(old_thread_id, {}).get("title", "未命名")
                if old_thread_id in conversations:
                    conversations[old_thread_id]["archived"] = True
                    conversations[old_thread_id]["continued_in"] = new_thread_id
                conversations[new_thread_id] = {
                    "title": old_title + " (续)",
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "message_count": 0,
                    "continued_from": old_thread_id,
                    "summary": summary[:200] if summary else "",
                }
                _save_conversations(conversations)

                # Build state with seed messages (summary + recent) + current input
                seed_messages.append(HumanMessage(content=user_input))
                state = {
                    "messages": seed_messages,
                    "active_agent": "supervisor",
                    "user_id": USER_ID,
                    "task_description": "",
                    "memory_context": memory_context,
                    "should_memorize": True,
                }
                state_override = True

                # Update config for the new thread
                config = {
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": settings.graph_recursion_limit,
                }

                user_turns = sum(
                    1 for m in existing_messages
                    if hasattr(m, "type") and m.type in ("human", "user")
                )
                logger.info(
                    "on_message: context forked",
                    old_thread=old_thread_id,
                    new_thread=new_thread_id,
                    turns=user_turns,
                )

                await cl.Message(
                    content=(
                        f"📝 对话较长（{user_turns}轮），已自动创建续接会话。\n"
                        "之前的对话已归档，可在设置中切换查看。"
                    )
                ).send()
        except Exception as e:
            logger.warning("on_message: context check failed, continuing", error=str(e))

    if not state_override:
        state = {
            "messages": [HumanMessage(content=user_input)],
            "active_agent": "supervisor",
            "user_id": USER_ID,
            "task_description": "",
            "memory_context": memory_context,
            "should_memorize": True,
        }

    response_msg = cl.Message(content="")
    full_response = ""
    current_agent = "supervisor"
    thinking_sent = False

    logger.info(
        "on_message: invoking graph",
        message_length=len(user_input),
        memory_context_chars=len(memory_context),
    )

    try:
        async for event in app.astream_events(state, config, version="v2"):
            kind = event.get("event", "")
            metadata = event.get("metadata", {})
            agent_name = metadata.get("langgraph_node", "")

            # Send a "thinking..." indicator on the very first event so the
            # user knows something is happening during tool execution.
            if not thinking_sent:
                thinking_sent = True
                await response_msg.stream_token("💭 ")

            # Detect agent switches
            if agent_name and agent_name != current_agent and agent_name in AGENT_DISPLAY:
                current_agent = agent_name
                await response_msg.stream_token(
                    f"\n\n**[{AGENT_DISPLAY[agent_name]}]**\n"
                )

            # Stream LLM tokens
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    token = str(chunk.content)
                    full_response += token
                    await response_msg.stream_token(token)

            # Show tool calls
            elif kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                await response_msg.stream_token(
                    f"\n🔧 调用工具: **{tool_name}**\n"
                )

            elif kind == "on_tool_end":
                tool_output = event.get("data", {}).get("output", "")
                if tool_output:
                    preview = str(tool_output)[:300]
                    if len(str(tool_output)) > 300:
                        preview += "..."
                    await response_msg.stream_token(f"📋 结果:\n{preview}\n")

        await response_msg.send()
        logger.info("on_message: response sent", response_length=len(full_response))

        # Update conversation metadata: set title from first user message,
        # increment message count after each exchange.
        if thread_id:
            conversations = _load_conversations()
            convo = conversations.get(thread_id, {})
            # Set title from first meaningful user message
            if not convo or convo.get("title") in ("未命名", "新对话", ""):
                title = _extract_title(user_input)
                if title:
                    _update_conversation(thread_id, title=title)
            _update_conversation(thread_id, increment_messages=True)

        # Phase 3: Store conversation in memory
        if full_response:
            try:
                memory_mgr.store_conversation(USER_ID, user_input, full_response)
                logger.info("on_message: conversation stored to memory")
            except Exception as e:
                logger.error("on_message: memory storage failed", error=str(e))

    except RecursionError as e:
        logger.error("on_message: recursion limit hit", error=str(e))
        if full_response:
            await response_msg.stream_token(
                "\n\n⚠️ 任务过长已被截断。当前回复已包含部分结果，"
                "可以换个方式继续提问。"
            )
            await response_msg.send()
        else:
            await cl.Message(
                content=(
                    "⚠️ 助手执行了太多步骤还没有完成任务。\n\n"
                    "建议：将复杂任务拆分为多个小步骤分别提问。"
                )
            ).send()

    except TimeoutError as e:
        logger.error("on_message: DeepSeek API timeout", error=str(e))
        if full_response:
            await response_msg.stream_token(
                "\n\n⏱️ 响应超时，已显示部分结果。可以继续追问或重试。"
            )
            await response_msg.send()
        else:
            await cl.Message(
                content="⏱️ DeepSeek API 响应超时，请稍后重试。如果持续出现，尝试缩短问题。"
            ).send()

    except Exception as e:
        error_str = str(e).lower()
        logger.error("on_message: streaming failed", error=str(e))

        if "rate_limit" in error_str or "rate" in error_str:
            user_msg = "⏳ API 频率限制，请等待几秒后重试。"
        elif "connection" in error_str or "timeout" in error_str:
            user_msg = "🔌 网络连接异常，请检查网络后重试。"
        elif "recursion" in error_str:
            user_msg = "🔄 任务步骤过多，请将问题拆分为更小的步骤重试。"
        else:
            user_msg = f"❌ 处理消息时出错：{str(e)[:200]}\n\n请重试或刷新页面。"

        if full_response:
            # Stream partial response if we got something before the error
            try:
                await response_msg.stream_token(f"\n\n⚠️ (回复中断) {user_msg}")
                await response_msg.send()
                full_response += f"\n\n⚠️ (回复中断) {user_msg}"
            except Exception:
                await cl.Message(content=user_msg).send()
        else:
            await cl.Message(content=user_msg).send()


@cl.on_chat_end
async def on_chat_end() -> None:
    """Clean up when the chat session ends."""
    logger.info("on_chat_end: session ended")


@cl.on_settings_update
async def on_settings_update(settings: dict) -> None:
    """Handle ChatSettings changes — conversation switching.

    Switches the current session to a different conversation and immediately
    replays its history in the UI. No page refresh needed.
    """
    selected = settings.get("conversation_switch", "")
    if not selected or selected == "__none__":
        return

    # Validate: must be "new" or a known thread_id
    conversations = _load_conversations()
    if selected != "new" and selected not in conversations:
        logger.warning(
            "on_settings_update: invalid selection, ignoring",
            selected=selected,
        )
        return

    session_id = cl.context.session.id
    current_thread = cl.user_session.get("thread_id")

    # No-op if selecting the already-active conversation
    if selected == current_thread:
        return

    # ── "new" = start a fresh conversation ──
    if selected == "new":
        new_thread_id = str(uuid.uuid4())
        thread_map = _load_thread_map()
        thread_map[session_id] = new_thread_id
        thread_map["__last_active__"] = new_thread_id
        _save_thread_map(thread_map)
        cl.user_session.set("thread_id", new_thread_id)
        conversations.pop("new", None)
        _save_conversations(conversations)
        logger.info(
            "on_settings_update: new conversation",
            session_id=session_id,
            thread_id=new_thread_id,
        )
        await cl.Message(
            content=(
                "✨ **新对话已开始！** 下方发送消息即可开始全新对话。\n\n"
                "💡 之前的对话记录不会丢失，可在设置中随时切换回来。"
            )
        ).send()
        return

    # ── Switch to an existing conversation ──
    convo = conversations.get(selected, {})
    title = convo.get("title", "未命名")
    count = convo.get("message_count", 0)

    # Update thread mapping so the next message goes to this conversation
    thread_map = _load_thread_map()
    thread_map[session_id] = selected
    thread_map["__last_active__"] = selected
    _save_thread_map(thread_map)
    cl.user_session.set("thread_id", selected)

    logger.info(
        "on_settings_update: switched conversation",
        session_id=session_id,
        thread_id=selected,
        title=title,
    )

    # Don't replay messages — the user asked for clean switching.
    # The current conversation is already saved (checkpointer).
    # The next user message will go to the selected conversation.
    await cl.Message(
        content=(
            f"📋 **已切换到**: {title}（{count} 条消息）\n\n"
            "发送任意消息即可继续此对话。\n"
            "💡 如需查看历史记录，刷新页面即可。"
        )
    ).send()
