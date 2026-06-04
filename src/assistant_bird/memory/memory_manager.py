"""Memory orchestrator — coordinates all three memory tiers."""



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

    def get_context(self, query: str, user_id: str) -> str:
        """Build combined memory context for injection into the LLM prompt.

        Searches all three memory tiers in parallel-ish sequence and
        returns a compact context string for the supervisor.

        Args:
            query: The user's current message (used for semantic search).
            user_id: User identifier.

        Returns:
            Context string suitable for injection into system prompt,
            or empty string if no memories found.
        """
        parts: list[str] = []

        # Tier 1: Personal facts from Mem0
        mem0 = get_mem0_client()
        if mem0.enabled:
            facts = mem0.search(query, user_id, limit=10)
            if facts:
                lines = ["## 用户个人信息/偏好 (长期记忆)"]
                total = 0
                for f in facts:
                    memory_text = f.get("memory", "")
                    if total + len(memory_text) > MAX_FACT_CHARS:
                        break
                    lines.append(f"- {memory_text}")
                    total += len(memory_text)
                parts.append("\n".join(lines))

        # Tier 2: Document knowledge from Chroma
        vector = get_vector_store()
        docs = vector.search(query, user_id, n_results=3)
        if docs:
            lines = ["## 相关知识文档"]
            total = 0
            for d in docs:
                content = d.get("content", "")
                if total + len(content) > MAX_DOC_CHARS:
                    break
                lines.append(f"- {content}")
                total += len(content)
            parts.append("\n".join(lines))

        # Tier 3: Recent conversation history
        conv_db = get_conversation_db()
        history = conv_db.get_summary_for_context(user_id, num_turns=MAX_HISTORY_TURNS)
        if history:
            parts.append(history)

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
