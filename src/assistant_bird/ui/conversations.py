"""Conversation metadata persistence and session→thread routing.

This module owns the data layer for the conversation switcher:
- thread_map.json   — session_id → thread_id mapping
- conversations.json — per-thread metadata (title, timestamps, message counts)

All functions are pure data I/O — no UI framework dependencies.
Message retrieval and rendering are handled by server/routes.py and
the desktop frontend respectively.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

# ── File paths ────────────────────────────────────────────────────────────


def _get_data_path(filename: str) -> Path:
    """Return a path under the app data directory, with CWD fallback."""
    from assistant_bird.app_dir import get_app_dir

    app_dir = get_app_dir()
    return app_dir / "data" / filename


def _resolve_thread_map_path() -> Path:
    """Resolve thread_map.json path: app_dir first, CWD fallback."""
    cwd_path = Path("data/thread_map.json")
    if cwd_path.exists():
        return cwd_path
    return _get_data_path("thread_map.json")


def _resolve_conversations_path() -> Path:
    """Resolve conversations.json path: app_dir first, CWD fallback."""
    cwd_path = Path("data/conversations.json")
    if cwd_path.exists():
        return cwd_path
    return _get_data_path("conversations.json")

# ── Conversation index cache ──────────────────────────────────────────────

_conversations_cache: dict[str, dict] | None = None


# ── Thread map ────────────────────────────────────────────────────────────


def load_thread_map() -> dict[str, str]:
    """Load the session_id → thread_id mapping from disk."""
    try:
        if _resolve_thread_map_path().exists():
            return json.loads(_resolve_thread_map_path().read_text())
    except Exception:
        pass
    return {}


def save_thread_map(data: dict[str, str]) -> None:
    """Save the session_id → thread_id mapping to disk."""
    _resolve_thread_map_path().parent.mkdir(parents=True, exist_ok=True)
    _resolve_thread_map_path().write_text(json.dumps(data))


# ── Conversation metadata ─────────────────────────────────────────────────


def load_conversations() -> dict[str, dict]:
    """Load conversation metadata index from cache or disk."""
    global _conversations_cache
    if _conversations_cache is not None:
        return _conversations_cache
    try:
        if _resolve_conversations_path().exists():
            _conversations_cache = json.loads(_resolve_conversations_path().read_text())
            return _conversations_cache
    except Exception:
        pass
    _conversations_cache = {}
    return _conversations_cache


def save_conversations(data: dict[str, dict]) -> None:
    """Save conversation index to disk and update cache."""
    global _conversations_cache
    _conversations_cache = data
    _resolve_conversations_path().parent.mkdir(parents=True, exist_ok=True)
    _resolve_conversations_path().write_text(json.dumps(data, ensure_ascii=False, indent=2))


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

