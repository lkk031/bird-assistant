"""LangGraph checkpoint management — persistent SQLite-backed checkpointer.

Uses langgraph-checkpoint-sqlite's AsyncSqliteSaver for cross-session
persistence with async support. Graph state survives server restarts.
"""

import asyncio
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# Compatibility patch: aiosqlite.Connection wraps sqlite3.Connection but
# doesn't expose .is_alive() — required by AsyncSqliteSaver.setup().
# The method exists in CPython's sqlite3 module (3.12+) but is missing
# in some builds (e.g. Anaconda).
# .is_alive() is used to check whether the connection's background thread
# has been started. If not yet started, setup() calls `await self.conn`
# to start it. If already started, setup() skips directly to SQL execution.
if not hasattr(aiosqlite.Connection, "is_alive"):
    def _is_alive(self) -> bool:
        """Return True if the connection's background thread is running."""
        return getattr(self, "_running", False)

    aiosqlite.Connection.is_alive = _is_alive  # type: ignore[assignment]

from assistant_bird.config import get_settings
from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

# Module-level connection reference to keep the aiosqlite connection alive.
_conn: aiosqlite.Connection | None = None


async def create_checkpointer(db_path: str | None = None) -> BaseCheckpointSaver:
    """Create a persistent async SQLite-backed LangGraph checkpointer.

    Graph state is persisted across server restarts.
    Each thread_id (conversation session) is stored independently.

    Args:
        db_path: Path to the SQLite checkpoint database.
                 Defaults to settings.checkpoint_db_path.

    Returns:
        An AsyncSqliteSaver for persisting graph state.
    """
    global _conn

    if db_path is None:
        db_path = str(get_settings().checkpoint_db_path)

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Close any previous connection before opening a new one
    if _conn is not None:
        try:
            await _conn.close()
        except Exception:
            pass

    _conn = await aiosqlite.connect(str(path))
    checkpointer = AsyncSqliteSaver(_conn)

    logger.info("create_checkpointer: AsyncSqliteSaver ready", db_path=str(path))
    return checkpointer


def create_checkpointer_sync(db_path: str | None = None) -> BaseCheckpointSaver:
    """Synchronous wrapper for create_checkpointer.

    Uses asyncio.run() to create the async checkpointer.
    Suitable for use in synchronous contexts.
    """
    return asyncio.run(create_checkpointer(db_path))
