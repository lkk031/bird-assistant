"""Mem0 API client wrapper — personal facts and long-term memory."""


from mem0 import MemoryClient

from assistant_bird.config import get_settings
from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)


class Mem0Client:
    """Wrapper around Mem0 managed API for personal fact memory.

    Mem0 automatically extracts structured facts from conversations
    and provides semantic search across stored facts.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client: MemoryClient | None = None
        self._enabled = bool(settings.mem0_api_key)
        self._api_key = settings.mem0_api_key

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def client(self) -> MemoryClient:
        if self._client is None:
            if not self._enabled:
                raise RuntimeError(
                    "Mem0 is not configured. Set MEM0_API_KEY in .env to enable."
                )
            self._client = MemoryClient(api_key=self._api_key)
        return self._client

    def search(self, query: str, user_id: str, limit: int = 10) -> list[dict]:
        """Semantic search for relevant facts in Mem0.

        Args:
            query: Natural language search query.
            user_id: User identifier for memory isolation.
            limit: Max number of results to return.

        Returns:
            List of memory dicts with 'memory', 'id', 'created_at', etc.
        """
        if not self._enabled:
            logger.info("mem0: search skipped (not configured)")
            return []

        try:
            results = self.client.search(query, user_id=user_id, limit=limit)
            logger.info("mem0: search", query=query, count=len(results))
            return results  # type: ignore[no-any-return]
        except Exception as e:
            logger.error("mem0: search failed", error=str(e))
            return []

    def add(
        self, messages: list[dict], user_id: str, metadata: dict | None = None
    ) -> list[dict]:
        """Add facts extracted from a conversation to Mem0.

        Mem0 automatically extracts structured facts from the raw messages.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            user_id: User identifier for memory isolation.
            metadata: Optional metadata to attach.

        Returns:
            List of created memory dicts.
        """
        if not self._enabled:
            logger.info("mem0: add skipped (not configured)")
            return []

        try:
            result = self.client.add(
                messages, user_id=user_id, metadata=metadata, output_format="v1.1"
            )
            logger.info("mem0: facts stored", count=len(result))
            return result  # type: ignore[no-any-return]
        except Exception as e:
            logger.error("mem0: add failed", error=str(e))
            return []

    def get_all(self, user_id: str) -> list[dict]:
        """Retrieve all stored facts for a user.

        Args:
            user_id: User identifier.

        Returns:
            List of all memory dicts.
        """
        if not self._enabled:
            return []

        try:
            results = self.client.get_all(user_id=user_id)
            return results  # type: ignore[no-any-return]
        except Exception as e:
            logger.error("mem0: get_all failed", error=str(e))
            return []

    def delete(self, memory_id: str) -> bool:
        """Delete a specific memory by ID.

        Args:
            memory_id: The memory ID to delete.

        Returns:
            True if successful.
        """
        if not self._enabled:
            return False

        try:
            self.client.delete(memory_id)
            logger.info("mem0: deleted", memory_id=memory_id)
            return True
        except Exception as e:
            logger.error("mem0: delete failed", error=str(e))
            return False


# Module-level singleton
_mem0: Mem0Client | None = None


def get_mem0_client() -> Mem0Client:
    """Get or create the Mem0 client singleton."""
    global _mem0
    if _mem0 is None:
        _mem0 = Mem0Client()
    return _mem0
