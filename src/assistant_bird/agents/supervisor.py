"""Supervisor agent — the routing brain of Assistant-Bird."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph_supervisor import create_supervisor

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


def create_supervisor_agent(
    model: BaseChatModel,
    agents: list[CompiledStateGraph],
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Create the supervisor agent that orchestrates all sub-agents.

    Uses langgraph-supervisor's create_supervisor which auto-generates
    handoff tools (transfer_to_<agent>) for each sub-agent.

    Args:
        model: The LLM model for the supervisor.
        agents: List of compiled sub-agent graphs.
        checkpointer: Optional checkpointer for state persistence.

    Returns:
        A compiled supervisor graph.
    """
    supervisor = create_supervisor(
        agents=agents,
        model=model,
        prompt=_build_supervisor_prompt,
        state_schema=AssistantState,
        output_mode="last_message",
        supervisor_name="supervisor",
    )

    return supervisor.compile(checkpointer=checkpointer)
