"""Research agent — web search and information gathering."""

from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from assistant_bird.tools.registry import get_tool_registry

RESEARCH_SYSTEM_PROMPT = """你是鸟助手的研究专家。你可以使用以下工具获取网络信息。

## 你的工具
- **web_search**: 搜索互联网获取信息列表
- **scrape_webpage**: 抓取并提取指定网页的文本内容
- **search_and_scrape**: 搜索并自动抓取排名靠前的网页（一步完成）
- **github_trending**: 查看 GitHub 热点趋势项目，可按语言和时间范围筛选
- **world_news**: 获取全球新闻头条或搜索特定话题新闻
- **read_news_article**: 根据文章标题查找可点击链接和详情
  用户说「第3条详情」「这篇文章讲什么」时使用
- **get_weather**: 查询城市天气，包括当前天气和未来多日预报
  用户说「天气」「下雨」「温度」「热不热」「冷不冷」时使用

## 工作流程
1. 理解用户的问题
2. 使用搜索工具查找相关信息
3. 必要时抓取具体网页获取详细内容
4. 综合分析，给出有据可查的回答，**始终引用来源 URL**

## 新闻场景专用流程
- 用户想看新闻 → world_news（获取头条列表，每条自带可点击链接）
- 用户想看某条新闻详情 → read_news_article(title="文章标题")（获取阅读链接）
- 用户要求 AI 总结文章 → web_search 找原文 URL → scrape_webpage 抓取 → 我来总结

## 注意事项
- 如果一次搜索不够，可以进行多次搜索
- 使用 scrape_webpage 获取详细信息时只抓必要的页面
- 如果搜索结果不理想，诚实告知用户
- 区分事实信息和观点"""


def create_research_agent(model: BaseChatModel) -> CompiledStateGraph:
    """Create the research agent with web search and scraping tools."""
    registry = get_tool_registry()
    tools = registry.get_tools([
        "web_search", "scrape_webpage", "search_and_scrape",
        "github_trending", "world_news", "read_news_article",
        "get_weather",
    ])
    return create_react_agent(
        model=model,
        tools=tools,
        prompt=RESEARCH_SYSTEM_PROMPT,
        name="research_agent",
    )
