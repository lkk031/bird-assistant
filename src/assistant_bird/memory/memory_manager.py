"""Memory orchestrator — coordinates all three memory tiers."""

from concurrent.futures import ThreadPoolExecutor

from assistant_bird.logging_config import get_logger
from assistant_bird.memory.conversation_db import get_conversation_db
from assistant_bird.memory.mem0_client import get_mem0_client
from assistant_bird.memory.vector_store import get_vector_store

logger = get_logger(__name__)

# Limit context to avoid blowing up the prompt
MAX_FACT_CHARS = 1000
MAX_DOC_CHARS = 1000
MAX_HISTORY_TURNS = 5


class MemoryManager:
    """Orchestrates memory operations across all three tiers.

    Tier 1: Mem0 — personal facts and preferences (managed API)
    Tier 2: Chroma — document/knowledge vector search (local)
    Tier 3: SQLite — conversation history (local)
    """

    # ── Per-tier search helpers (run in threads for parallelism) ──────

    @staticmethod
    def _search_mem0(query: str, user_id: str) -> str | None:
        """Search Mem0 for personal facts. Returns formatted block or None."""
        try:
            mem0 = get_mem0_client()
            if not mem0.enabled:
                return None
            facts = mem0.search(query, user_id, limit=10)
            if not facts:
                return None
            lines = ["## 用户个人信息/偏好 (长期记忆)"]
            total = 0
            for f in facts:
                memory_text = f.get("memory", "")
                if total + len(memory_text) > MAX_FACT_CHARS:
                    break
                lines.append(f"- {memory_text}")
                total += len(memory_text)
            return "\n".join(lines)
        except Exception:
            return None

    @staticmethod
    def _search_chroma(query: str, user_id: str) -> str | None:
        """Search Chroma vector store. Returns formatted block or None."""
        try:
            vector = get_vector_store()
            docs = vector.search(query, user_id, n_results=3)
            if not docs:
                return None
            lines = ["## 相关知识文档"]
            total = 0
            for d in docs:
                content = d.get("content", "")
                if total + len(content) > MAX_DOC_CHARS:
                    break
                lines.append(f"- {content}")
                total += len(content)
            return "\n".join(lines)
        except Exception:
            return None

    @staticmethod
    def _search_history(user_id: str) -> str | None:
        """Load recent conversation history from SQLite. Returns block or None."""
        try:
            conv_db = get_conversation_db()
            return conv_db.get_summary_for_context(user_id, num_turns=MAX_HISTORY_TURNS)
        except Exception:
            return None

    # ── Public API ────────────────────────────────────────────────────

    def get_context(self, query: str, user_id: str) -> str:
        """Build combined memory context for injection into the LLM prompt.

        Runs all three memory tiers in parallel via ThreadPoolExecutor.
        Total latency = max(tier1, tier2, tier3) instead of sum.

        Args:
            query: The user's current message (used for semantic search).
            user_id: User identifier.

        Returns:
            Context string suitable for injection into system prompt,
            or empty string if no memories found.
        """
        # Fire all three tiers concurrently. Each returns a string block
        # or None on failure/empty — errors are isolated per tier.
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_mem0 = executor.submit(self._search_mem0, query, user_id)
            future_chroma = executor.submit(self._search_chroma, query, user_id)
            future_history = executor.submit(self._search_history, user_id)

            parts: list[str] = []
            for result in (future_mem0.result(), future_chroma.result(), future_history.result()):
                if result:
                    parts.append(result)

        context = "\n\n".join(parts) if parts else ""
        total = sum(len(p) for p in parts)
        if context:
            logger.info("memory_manager: context built", tiers=len(parts), chars=total)
        return context

    def store_conversation(
        self, user_id: str, user_message: str, assistant_message: str
    ) -> None:
        """Store a conversation turn in the conversation log and Mem0.

        Args:
            user_id: User identifier.
            user_message: The user's message.
            assistant_message: The assistant's response.
        """
        conv_db = get_conversation_db()

        # Save to SQLite
        conv_db.save_message(user_id, "user", user_message)
        conv_db.save_message(user_id, "assistant", assistant_message)

        # Extract facts to Mem0 (best effort, non-blocking)
        mem0 = get_mem0_client()
        if mem0.enabled:
            try:
                mem0.add(
                    messages=[
                        {"role": "user", "content": user_message},
                        {"role": "assistant", "content": assistant_message},
                    ],
                    user_id=user_id,
                )
            except Exception as e:
                logger.error("memory_manager: mem0 extraction failed", error=str(e))

    def ingest_document(
        self, content: str, user_id: str, metadata: dict | None = None
    ) -> str:
        """Ingest a document into the vector store.

        Args:
            content: Text content to ingest.
            user_id: User identifier.
            metadata: Optional metadata.

        Returns:
            Document ID.
        """
        return get_vector_store().add_document(content, user_id, metadata)


# Module-level singleton
_memory_manager: MemoryManager | None = None


def get_memory_manager() -> MemoryManager:
    """Get or create the MemoryManager singleton."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
