"""SQLite conversation history — structured conversation logs."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from assistant_bird.config import get_settings
from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)


class ConversationDB:
    """SQLite-backed conversation history for searchable message logs."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = get_settings().sqlite_db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(db_path)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conv_user_id
                ON conversations(user_id, created_at)
            """)
            conn.commit()

    def save_message(
        self,
        user_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> int:
        """Save a single message to the conversation log.

        Args:
            user_id: User identifier.
            role: 'user' or 'assistant'.
            content: Message text content.
            metadata: Optional metadata dict.

        Returns:
            The row ID.
        """
        now = datetime.now(UTC).isoformat()
        meta_json = json.dumps(metadata or {})

        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO conversations (user_id, role, content, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, role, content, meta_json, now),
            )
            conn.commit()
            return cursor.lastrowid

    def get_recent(
        self, user_id: str, limit: int = 20
    ) -> list[dict]:
        """Get the most recent conversations for a user.

        Args:
            user_id: User identifier.
            limit: Max number of messages to return.

        Returns:
            List of message dicts.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT id, user_id, role, content, metadata, created_at
                   FROM conversations
                   WHERE user_id = ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (user_id, limit),
            ).fetchall()

        results = []
        for row in reversed(rows):
            results.append({
                "id": row["id"],
                "role": row["role"],
                "content": row["content"][:200],
                "metadata": json.loads(row["metadata"]),
                "created_at": row["created_at"],
            })
        return results

    def search(
        self, user_id: str, query: str, limit: int = 10
    ) -> list[dict]:
        """Full-text search in conversation history.

        Args:
            user_id: User identifier.
            query: Search string (LIKE match).
            limit: Max results.

        Returns:
            List of matching message dicts.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT id, role, content, metadata, created_at
                   FROM conversations
                   WHERE user_id = ? AND content LIKE ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (user_id, f"%{query}%", limit),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "role": row["role"],
                "content": row["content"][:500],
                "metadata": json.loads(row["metadata"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def get_summary_for_context(self, user_id: str, num_turns: int = 5) -> str:
        """Get a condensed summary of recent conversations for LLM context.

        Args:
            user_id: User identifier.
            num_turns: Number of recent message pairs to include.

        Returns:
            Condensed context string for injection into system prompt.
        """
        messages = self.get_recent(user_id, limit=num_turns * 2)
        if not messages:
            return ""

        lines = ["[Recent conversation history]"]
        for msg in messages:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            content = msg["content"][:150]
            lines.append(f"{role_label}: {content}")
        return "\n".join(lines)


# Module-level singleton
_conversation_db: ConversationDB | None = None


def get_conversation_db() -> ConversationDB:
    """Get or create the ConversationDB singleton."""
    global _conversation_db
    if _conversation_db is None:
        _conversation_db = ConversationDB()
    return _conversation_db
