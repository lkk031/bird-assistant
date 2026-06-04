"""LangGraph graph builder — assembles the assistant graph."""

from langgraph.graph.state import CompiledStateGraph

from assistant_bird.agents.filesystem import create_file_ops_agent
from assistant_bird.agents.general import create_general_agent
from assistant_bird.agents.memory_agent import create_memory_agent
from assistant_bird.agents.research import create_research_agent
from assistant_bird.agents.supervisor import create_supervisor_agent
from assistant_bird.graph.checkpointer import create_checkpointer
from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)


def build_assistant_graph(model) -> CompiledStateGraph:
    """Build the full supervisor-based multi-agent graph (Phase 2).

    Creates 4 sub-agents (general, research, file_ops, memory) and wraps them
    in a supervisor that routes user messages to the appropriate specialist.

    Args:
        model: A configured ChatDeepSeek instance.

    Returns:
        A compiled LangGraph supervisor graph with in-memory checkpointer.
    """
    logger.info("build_assistant_graph: creating sub-agents")

    # Create all sub-agents
    sub_agents = [
        create_general_agent(model),
        create_research_agent(model),
        create_file_ops_agent(model),
        create_memory_agent(model),
    ]

    # Create in-memory checkpointer (swap to SqliteSaver for persistence)
    checkpointer = create_checkpointer()

    # Assemble supervisor graph
    supervisor = create_supervisor_agent(
        model=model,
        agents=sub_agents,
        checkpointer=checkpointer,
    )

    logger.info(
        "build_assistant_graph: supervisor graph compiled",
        agent_count=len(sub_agents),
    )
    return supervisor
