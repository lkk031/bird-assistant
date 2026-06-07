"""In-memory session management for the desktop app.

Replaces Chainlit's cl.user_session / cl.context.session with a simple
singleton session. Since this is a single-user desktop application, we
don't need multi-user session isolation — one session per process lifetime.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from langgraph.graph.state import CompiledStateGraph


@dataclass
class AppSession:
    """Holds the runtime state for the current desktop session."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    thread_id: str | None = None
    app: CompiledStateGraph | None = None
    model: Any = None  # BaseChatModel

    def set(self, key: str, value: Any) -> None:
        """Set a session value (compatible with cl.user_session.set)."""
        setattr(self, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a session value (compatible with cl.user_session.get)."""
        return getattr(self, key, default)


# Singleton — created once when the server starts, shared across all routes.
_session: AppSession | None = None


def get_session() -> AppSession:
    """Return the global AppSession singleton, creating it if needed."""
    global _session
    if _session is None:
        _session = AppSession()
    return _session


def reset_session() -> None:
    """Reset the global session (useful for testing)."""
    global _session
    _session = AppSession()
