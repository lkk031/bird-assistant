"""LangGraph state definitions for Assistant-Bird."""

from collections.abc import Sequence
from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AssistantState(TypedDict):
    """Shared state flowing through the assistant graph.

    Attributes:
        messages: Conversation history, auto-reduced via add_messages reducer.
        active_agent: Name of the currently executing agent (for UI display).
        user_id: Identifier for the current user (memory scoping).
        task_description: What the supervisor decided needs to be done.
        memory_context: Combined context from all memory tiers.
        should_memorize: Whether this turn's facts should be stored in long-term memory.
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    active_agent: str
    user_id: str
    task_description: str
    memory_context: str
    should_memorize: bool
