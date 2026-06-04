"""General-purpose conversational agent."""

from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

GENERAL_SYSTEM_PROMPT = """你是鸟助手的通用对话专家。你负责处理不需要特殊工具的日常对话。

## 你的职责
- 进行自然、友好的中文对话
- 回答常识性问题
- 提供建议、分析和解释
- 帮助写作、翻译、总结
- 处理用户的各种日常需求

## 交流风格
- 友好、耐心、专业
- 默认使用中文回复
- 如果用户的问题需要搜索网络或操作文件，请告知用户并建议切换"""


def create_general_agent(model: BaseChatModel) -> CompiledStateGraph:
    """Create the general conversation agent (no tools)."""
    return create_react_agent(
        model=model,
        tools=[],
        prompt=GENERAL_SYSTEM_PROMPT,
        name="general_agent",
    )
