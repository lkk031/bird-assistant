"""Tool registry — central catalog of all available tools."""

from langchain_core.tools import BaseTool

from assistant_bird.tools.web_scraper import scrape_webpage, search_and_scrape
from assistant_bird.tools.web_search import web_search


class ToolRegistry:
    """Registry of all tools available to agents.

    Usage:
        registry = ToolRegistry()
        tools = registry.get_tools(["web_search", "scrape_webpage"])
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {
            "web_search": web_search,
            "scrape_webpage": scrape_webpage,
            "search_and_scrape": search_and_scrape,
        }

    def get_tool(self, name: str) -> BaseTool:
        """Get a single tool by name."""
        if name not in self._tools:
            available = list(self._tools.keys())
            raise KeyError(f"Tool '{name}' not found. Available: {available}")
        return self._tools[name]

    def get_tools(self, names: list[str]) -> list[BaseTool]:
        """Get multiple tools by name."""
        return [self.get_tool(n) for n in names]

    def list_tools(self) -> list[str]:
        """Return all registered tool names."""
        return list(self._tools.keys())

    def register(self, name: str, tool: BaseTool) -> None:
        """Register a new tool."""
        self._tools[name] = tool


# Global singleton
_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get or create the global tool registry singleton."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
