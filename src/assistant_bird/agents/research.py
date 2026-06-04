"""Research agent — web search and information gathering."""

from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from assistant_bird.tools.registry import get_tool_registry

RESEARCH_SYSTEM_PROMPT = """你是鸟助手的研究专家。你可以使用网络搜索工具来获取最新信息。

## 你的职责
- 搜索互联网获取信息
- 事实核查和信息验证
- 查找新闻、数据、文档
- 对比多个信息来源

## 工作流程
1. 理解用户的问题
2. 使用 web_search 工具搜索相关信息
3. 综合分析搜索结果
4. 给出有据可查的回答，**始终引用来源 URL**

## 注意事项
- 如果一次搜索不够，可以进行多次搜索
- 如果搜索结果不理想，诚实告知用户
- 区分事实信息和观点"""


def create_research_agent(model: BaseChatModel) -> CompiledStateGraph:
    """Create the research agent with web_search tool."""
    registry = get_tool_registry()
    tools = registry.get_tools(["web_search"])
    return create_react_agent(
        model=model,
        tools=tools,
        prompt=RESEARCH_SYSTEM_PROMPT,
        name="research_agent",
    )
