"""DuckDuckGo web search tool for agents."""

from duckduckgo_search import DDGS
from langchain_core.tools import tool

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)


@tool
def web_search(query: str, num_results: int = 5) -> str:
    """Search the web using DuckDuckGo and return formatted results.

    Args:
        query: The search query string.
        num_results: Number of results to return (default 5, max 10).

    Returns:
        Formatted search results with titles, snippets, and URLs.
    """
    num_results = min(num_results, 10)
    logger.info("web_search: searching", query=query, num_results=num_results)

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num_results))

        if not results:
            return f"No results found for: {query}"

        formatted = [f"## Search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            body = r.get("body", "No description")
            href = r.get("href", "")
            formatted.append(f"{i}. **{title}**")
            formatted.append(f"   {body}")
            if href:
                formatted.append(f"   URL: {href}")
            formatted.append("")

        return "\n".join(formatted)
    except Exception as e:
        logger.error("web_search: failed", error=str(e))
        return f"Search failed: {str(e)}"
