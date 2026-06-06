"""LangGraph state definitions for Assistant-Bird."""

from collections.abc import Sequence
from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langgraph.managed import IsLastStep, RemainingSteps
from typing_extensions import TypedDict


class AssistantState(TypedDict):
    """Shared state flowing through the assistant graph.

    Attributes:
        messages: Conversation history, auto-reduced via add_messages reducer.
        is_last_step: Managed field — True when the agent should stop.
        remaining_steps: Managed field — steps remaining before forced stop.
        active_agent: Name of the currently executing agent (for UI display).
        user_id: Identifier for the current user (memory scoping).
        task_description: What the supervisor decided needs to be done.
        memory_context: Combined context from all memory tiers.
        should_memorize: Whether this turn's facts should be stored in long-term memory.
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    is_last_step: IsLastStep
    remaining_steps: RemainingSteps
    active_agent: str
    user_id: str
    task_description: str
    memory_context: str
    should_memorize: bool
