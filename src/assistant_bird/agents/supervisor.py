"""Supervisor agent — the routing brain of Assistant-Bird.

Builds a multi-agent supervisor graph where the supervisor LLM routes
user messages to specialized sub-agents. Each sub-agent is called with
ainvoke() (async) to support async tools.
"""

import inspect
from collections.abc import Callable
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt.chat_agent_executor import (
    Prompt,
    StateSchemaType,
    create_react_agent,
)
from langgraph_supervisor.handoff import (
    create_handoff_back_messages,
    create_handoff_tool,
)

from assistant_bird.graph.state import AssistantState

SUPERVISOR_SYSTEM_PROMPT = """你是"鸟助手" (Assistant-Bird) 的主管 Agent。
一个个人 AI 助手的核心调度者，负责将任务委派给最合适的专业 Agent。

## 你的团队
你可以将任务委派给以下专业 Agent：
- **general_agent**: 通用对话、写作、推理、总结 — 日常对话首选
- **research_agent**: 网络搜索、信息获取、事实核查 — 需要最新信息时使用
- **file_ops_agent**: 文件管理（读写/复制/移动/删除/追加）、目录浏览、文件搜索 — 操作本地文件时使用
- **memory_agent**: 记忆存取、偏好管理 — 记住或回忆信息时使用

## 工作流程
1. 仔细理解用户的请求
2. 判断最适合处理该请求的 Agent
3. 将任务委派给该 Agent
4. Agent 完成后，评估结果是否需要进一步处理
5. 向用户呈现最终结果（由最后发言的 Agent 直接回复用户）

## 委派策略
- 简单对话、写作、分析 → general_agent
- 搜索信息、查新闻、找资料 → research_agent
- 读文件、列目录 → file_ops_agent
- 记东西、回忆偏好 → memory_agent
- 用户问题可能被拆分为多个子任务，依次委派不同 Agent

## 交流风格
- 默认中文，友好专业
- 多 Agent 协作时，最终回复保持连贯流畅"""

OutputMode = Literal["full_history", "last_message"]


def _build_supervisor_prompt(state: dict[str, Any]) -> list:
    """Build the supervisor's message list from state.

    Injects memory_context (if present) as a leading SystemMessage so
    the supervisor sees the user's long-term facts and preferences
    before making routing decisions.

    This is a Callable prompt — create_react_agent accepts callables
    that receive the full state dict and return a message list.
    """
    messages: list = []

    # Inject memory context as the first system message (transient per-turn —
    # it's set in on_message, not persisted across turns)
    memory_context = state.get("memory_context", "")
    if memory_context:
        messages.append(SystemMessage(content=memory_context))

    # Core supervisor instructions
    messages.append(SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT))

    # Conversation history (includes the new HumanMessage from this turn)
    existing = state.get("messages", [])
    if existing:
        messages.extend(existing)

    return messages


def _make_call_agent(
    agent: CompiledStateGraph,
    output_mode: OutputMode,
    add_handoff_back_messages: bool,
    supervisor_name: str,
) -> Callable[[dict], dict]:
    """Create an **async** sub-agent call function.

    Uses ainvoke() instead of invoke() so async tools (like our httpx-based
    search/scrape tools) work correctly. The langgraph-supervisor library's
    version uses invoke() which raises "StructuredTool does not support
    sync invocation" for async-only @tool functions.
    """
    if output_mode not in ("full_history", "last_message"):
        raise ValueError(
            f"Invalid agent output mode: {output_mode}. "
            f"Needs to be one of ('full_history', 'last_message')"
        )

    async def call_agent(state: dict) -> dict:
        output = await agent.ainvoke(state)
        messages = output["messages"]

        if output_mode == "last_message":
            messages = messages[-1:]

        if add_handoff_back_messages:
            messages = list(messages)  # Don't mutate the original
            messages.extend(
                create_handoff_back_messages(agent.name, supervisor_name)
            )

        return {"messages": messages}

    return call_agent


def create_supervisor_agent(
    model: BaseChatModel,
    agents: list[CompiledStateGraph],
    checkpointer: BaseCheckpointSaver | None = None,
    tools: list[Callable | BaseTool] | None = None,
    prompt: Prompt | None = None,
    state_schema: StateSchemaType = AssistantState,
    output_mode: OutputMode = "last_message",
    add_handoff_back_messages: bool = True,
    supervisor_name: str = "supervisor",
) -> CompiledStateGraph:
    """Create the supervisor agent that orchestrates all sub-agents.

    Builds a multi-agent graph where a supervisor LLM routes to specialized
    sub-agents via auto-generated handoff tools. Sub-agents are called with
    ainvoke() to support async tools.

    Args:
        model: The LLM model for the supervisor.
        agents: List of compiled sub-agent graphs.
        checkpointer: Optional checkpointer for state persistence.
        tools: Optional additional tools for the supervisor.
        prompt: Optional prompt (str, SystemMessage, Callable, or Runnable).
                Defaults to _build_supervisor_prompt.
        state_schema: State schema for the supervisor graph.
        output_mode: "full_history" or "last_message" (default).
        add_handoff_back_messages: Whether to add handoff marker messages.
        supervisor_name: Name of the supervisor node.

    Returns:
        A compiled supervisor graph.
    """
    agent_names = set()
    for agent in agents:
        if agent.name is None or agent.name == "LangGraph":
            raise ValueError(
                "Please specify a name when you create your agent, "
                "either via `create_react_agent(..., name=agent_name)` "
                "or via `graph.compile(name=name)`."
            )
        if agent.name in agent_names:
            raise ValueError(
                f"Agent with name '{agent.name}' already exists. "
                "Agent names must be unique."
            )
        agent_names.add(agent.name)

    # Use default prompt if none provided
    if prompt is None:
        prompt = _build_supervisor_prompt

    # Create handoff tools (one per sub-agent)
    handoff_tools = [create_handoff_tool(agent_name=agent.name) for agent in agents]
    all_tools = (tools or []) + handoff_tools

    # Bind tools to model (disable parallel tool calls for cleaner routing)
    if (
        hasattr(model, "bind_tools")
        and "parallel_tool_calls" in inspect.signature(model.bind_tools).parameters
    ):
        model = model.bind_tools(all_tools, parallel_tool_calls=False)

    # Create the supervisor react agent
    supervisor_agent = create_react_agent(
        name=supervisor_name,
        model=model,
        tools=all_tools,
        prompt=prompt,
        state_schema=state_schema,
    )

    # Build the multi-agent graph
    builder = StateGraph(state_schema)
    builder.add_node(supervisor_agent)

    # Edge: START → supervisor
    builder.add_edge(START, supervisor_agent.name)

    # Add sub-agents as async nodes
    for agent in agents:
        builder.add_node(
            agent.name,
            _make_call_agent(
                agent,
                output_mode,
                add_handoff_back_messages,
                supervisor_name,
            ),
        )
        # Sub-agents always return control to the supervisor
        builder.add_edge(agent.name, supervisor_agent.name)

    # Compile (without checkpointer first, then with if provided)
    compiled = builder.compile(checkpointer=checkpointer)
    return compiled
