"""Conversation metadata persistence and session→thread routing.

This module owns the data layer for the conversation switcher:
- thread_map.json   — session_id → thread_id mapping
- conversations.json — per-thread metadata (title, timestamps, message counts)
- _replay_messages  — reads LangGraph state into the Chainlit UI
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import chainlit as cl
from chainlit.input_widget import Select

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

# ── File paths ────────────────────────────────────────────────────────────

THREAD_MAP_FILE = Path("data/thread_map.json")
CONVERSATIONS_FILE = Path("data/conversations.json")

# ── Conversation index cache ──────────────────────────────────────────────

_conversations_cache: dict[str, dict] | None = None


# ── Thread map ────────────────────────────────────────────────────────────


def load_thread_map() -> dict[str, str]:
    """Load the session_id → thread_id mapping from disk."""
    try:
        if THREAD_MAP_FILE.exists():
            return json.loads(THREAD_MAP_FILE.read_text())
    except Exception:
        pass
    return {}


def save_thread_map(data: dict[str, str]) -> None:
    """Save the session_id → thread_id mapping to disk."""
    THREAD_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    THREAD_MAP_FILE.write_text(json.dumps(data))


# ── Conversation metadata ─────────────────────────────────────────────────


def load_conversations() -> dict[str, dict]:
    """Load conversation metadata index from cache or disk."""
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


def save_conversations(data: dict[str, dict]) -> None:
    """Save conversation index to disk and update cache."""
    global _conversations_cache
    _conversations_cache = data
    CONVERSATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONVERSATIONS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def register_conversation(thread_id: str, title: str = "") -> None:
    """Add a new conversation to the metadata index."""
    conversations = load_conversations()
    now = datetime.now(UTC).isoformat()
    conversations[thread_id] = {
        "title": title or "未命名",
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    }
    save_conversations(conversations)


def ensure_conversation_exists(thread_id: str) -> None:
    """Lazy-register a conversation if it doesn't exist yet."""
    conversations = load_conversations()
    if thread_id not in conversations:
        register_conversation(thread_id)


def update_conversation(
    thread_id: str,
    *,
    title: str | None = None,
    increment_messages: bool = False,
) -> None:
    """Update a conversation's metadata (title, count, timestamp).

    Auto-registers the conversation if it doesn't exist yet.
    """
    ensure_conversation_exists(thread_id)
    conversations = load_conversations()
    now = datetime.now(UTC).isoformat()
    conversations[thread_id]["updated_at"] = now
    if title:
        conversations[thread_id]["title"] = title
    if increment_messages:
        conversations[thread_id]["message_count"] += 1
    save_conversations(conversations)


# ── Message replay ────────────────────────────────────────────────────────


async def replay_messages(app, thread_id: str) -> int:
    """Replay conversation history from LangGraph state into the Chainlit UI.

    Returns the number of messages replayed (0 if thread is empty or missing).
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
            "replay_messages: replaying history",
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
        logger.warning("replay_messages: replay failed", error=str(e))
        return 0


# ── Title extraction ──────────────────────────────────────────────────────


def extract_title(user_input: str) -> str:
    """Extract a meaningful conversation title from the first user message."""
    import re

    raw = user_input.strip()
    if not raw:
        return "对话"

    noise_prefixes = [
        "请帮我", "帮我", "请", "我想让你", "能不能",
        "你可以", "你可以帮我", "麻烦你", "麻烦",
    ]
    for prefix in noise_prefixes:
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break

    raw = raw.lstrip("，,。. ")

    if len(raw) > 30:
        truncated = raw[:30]
        match = re.search(r"[，,。.!！?？\s][^，,。.!！?？\s]*$", truncated)
        if match and match.start() > 10:
            raw = truncated[:match.start()]
        else:
            raw = truncated

    return raw.strip() or user_input.strip()[:30]


# ── Conversation selector widget ──────────────────────────────────────────


def build_conversation_select(current_thread_id: str) -> list:
    """Build a ChatSettings Select widget for conversation switching."""
    conversations = load_conversations()
    sorted_convos = sorted(
        conversations.items(),
        key=lambda kv: kv[1].get("updated_at", ""),
        reverse=True,
    )

    items: dict[str, str] = {}

    active_convos = [
        (tid, meta) for tid, meta in sorted_convos
        if meta.get("message_count", 0) > 0
    ]

    for tid, meta in active_convos[:30]:
        title = meta.get("title", "未命名")
        updated = meta.get("updated_at", "")[:10]
        count = meta.get("message_count", 0)
        prefix = "📦 " if meta.get("archived") else ""
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

    # Always include the current conversation, even if it has 0 messages
    current_is_new = current_thread_id not in [v for v in items.values()]
    if current_is_new:
        convo_meta = conversations.get(current_thread_id, {})
        title = convo_meta.get("title", "新对话")
        items[f"🆕 {title}"] = current_thread_id

    if len(items) == 0:
        items["(暂无历史对话)"] = "__none__"

    # Resolve initial_value to match current_thread_id
    initial = current_thread_id if current_is_new else None
    if initial is None:
        for _label, value in items.items():
            if value == current_thread_id:
                initial = value
                break
    if initial is None and items:
        initial = next(iter(items.values()))

    return [
        Select(
            id="conversation_switch",
            label="📋 对话历史",
            items=items,
            initial_value=initial,
            description="选择历史对话或创建新对话",
        )
    ]
