"""Memory management agent — manages user's long-term memory."""

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from assistant_bird.memory.mem0_client import get_mem0_client
from assistant_bird.memory.vector_store import get_vector_store

MEMORY_SYSTEM_PROMPT = """你是鸟助手的记忆管理专家。你负责管理用户的长期记忆和知识库。

## 你的职责
- 记住用户的重要信息、偏好、习惯
- 当用户询问"我之前说过什么"时，搜索记忆
- 帮助用户在知识库中存储和查找文档
- 当记忆功能未配置时（未设置MEM0_API_KEY），告知用户如何开启

## 你的工具
- recall_memories: 搜索用户的长期记忆
- remember_fact: 记住一条重要信息
- search_documents: 在用户的知识库中搜索
- list_facts: 列出所有已存储的记忆

## 重要提示
- 如果对"记一下xxx"的请求，请使用 remember_fact
- 如果对"我之前说过什么""还记得xxx吗"的请求，请使用 recall_memories"""


@tool
def recall_memories(query: str, user_id: str = "local_user") -> str:
    """Search the user's long-term memory for relevant facts and preferences.

    Args:
        query: What to search for in natural language.
        user_id: User identifier (default: local_user).

    Returns:
        List of relevant memories found, or message if none.
    """
    mem0 = get_mem0_client()
    if not mem0.enabled:
        return (
            "记忆功能未启用。请设置 MEM0_API_KEY 环境变量来开启。\n"
            "获取地址: https://app.mem0.ai/"
        )
    facts = mem0.search(query, user_id, limit=10)
    if not facts:
        return f"没有找到与 '{query}' 相关的记忆。"

    lines = [f"找到 {len(facts)} 条相关记忆:"]
    for i, f in enumerate(facts, 1):
        lines.append(f"{i}. {f.get('memory', str(f))}")
    return "\n".join(lines)


@tool
def remember_fact(fact: str, user_id: str = "local_user") -> str:
    """Store an important fact or preference in long-term memory.

    Args:
        fact: The fact to remember, phrased as a clear statement.
        user_id: User identifier (default: local_user).

    Returns:
        Confirmation message.
    """
    mem0 = get_mem0_client()
    if not mem0.enabled:
        return "记忆功能未启用。请设置 MEM0_API_KEY 来开启。"
    mem0.add(
        messages=[{"role": "user", "content": f"请记住: {fact}"}],
        user_id=user_id,
    )
    return f"✅ 已记住: {fact}"


@tool
def search_documents(query: str, user_id: str = "local_user") -> str:
    """Search the user's knowledge base (documents, notes).

    Args:
        query: Search query in natural language.
        user_id: User identifier (default: local_user).

    Returns:
        Relevant document contents.
    """
    vector = get_vector_store()
    docs = vector.search(query, user_id, n_results=5)
    if not docs:
        return f"知识库中没有找到与 '{query}' 相关的内容。"

    lines = [f"找到 {len(docs)} 条相关内容:"]
    for i, d in enumerate(docs, 1):
        lines.append(f"\n{i}. {d['content'][:300]}")
    return "\n".join(lines)


@tool
def list_facts(user_id: str = "local_user") -> str:
    """List all stored personal facts and preferences.

    Args:
        user_id: User identifier (default: local_user).

    Returns:
        All stored memories.
    """
    mem0 = get_mem0_client()
    if not mem0.enabled:
        return "记忆功能未启用。"
    facts = mem0.get_all(user_id)
    if not facts:
        return "还没有存储任何记忆。"
    lines = [f"共有 {len(facts)} 条记忆:"]
    for i, f in enumerate(facts, 1):
        lines.append(f"{i}. {f.get('memory', str(f))}")
    return "\n".join(lines)


def create_memory_agent(model: BaseChatModel) -> CompiledStateGraph:
    """Create the memory management agent with real memory tools."""
    return create_react_agent(
        model=model,
        tools=[recall_memories, remember_fact, search_documents, list_facts],
        prompt=MEMORY_SYSTEM_PROMPT,
        name="memory_agent",
    )
