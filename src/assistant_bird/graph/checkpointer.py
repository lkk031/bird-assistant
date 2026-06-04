"""LangGraph checkpoint management.

Currently uses in-memory checkpointer. For SQLite persistence, install
the langgraph-checkpoint-sqlite package and swap to SqliteSaver.
"""

from langgraph.checkpoint.memory import InMemorySaver

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)


def create_checkpointer() -> InMemorySaver:
    """Create an in-memory LangGraph checkpointer.

    Returns:
        An InMemorySaver for persisting graph state within a session.

    Note:
        Swap to SqliteSaver from langgraph-checkpoint-sqlite for
        cross-session persistence when needed.
    """
    logger.info("create_checkpointer: creating InMemorySaver")
    return InMemorySaver()
