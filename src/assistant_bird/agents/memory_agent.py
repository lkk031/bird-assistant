"""Memory management agent — long-term user memory (Phase 3 placeholder)."""

from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

MEMORY_SYSTEM_PROMPT = """你是鸟助手的记忆管理专家。你负责管理用户的长期记忆。

## 你的职责
- 从对话中提取重要信息并记录
- 回忆用户之前提到的偏好和事实
- 管理用户的知识库

## 当前状态
记忆系统（Mem0 + Chroma）正在开发中。目前你可以：
- 在对话中主动识别值得记住的信息
- 提示用户"这个信息值得记住"
- 告知用户完整的记忆功能即将上线
- 当用户询问之前提到的事情时，诚实告知记忆功能尚未启用"""


def create_memory_agent(model: BaseChatModel) -> CompiledStateGraph:
    """Create the memory management agent (placeholder for Phase 3)."""
    return create_react_agent(
        model=model,
        tools=[],
        prompt=MEMORY_SYSTEM_PROMPT,
        name="memory_agent",
    )
