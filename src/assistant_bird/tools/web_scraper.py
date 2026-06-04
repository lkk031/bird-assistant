"""Web scraping tool using httpx + BeautifulSoup."""

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

TIMEOUT = 10.0
MAX_CONTENT_LENGTH = 8000
USER_AGENT = (
    "Mozilla/5.0 (compatible; AssistantBird/0.1; +https://github.com/lkk031/bird-assistant)"
)


@tool
def scrape_webpage(url: str) -> str:
    """Fetch and extract text content from a web page.

    Strips out scripts, styles, navigation elements and returns clean text.
    Useful for getting the content of a specific URL after a search.

    Args:
        url: The full URL to scrape (must start with http:// or https://).

    Returns:
        Extracted text content, truncated if very large.
    """
    if not url.startswith(("http://", "https://")):
        return f"Error: Invalid URL '{url}'. Must start with http:// or https://"

    logger.info("scrape_webpage: fetching", url=url)

    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            response = client.get(
                url,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
    except httpx.TimeoutException:
        return f"Error: Request to {url} timed out after {TIMEOUT}s."
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} when fetching {url}."
    except Exception as e:
        return f"Error fetching {url}: {str(e)}"

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "text/plain" not in content_type:
        return (
            f"Error: URL returned non-text content type '{content_type}'. "
            "Cannot scrape binary files."
        )

    # Parse and clean HTML
    soup = BeautifulSoup(response.text, "html.parser")

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
        tag.decompose()

    # Extract text from main content or body
    main = soup.find("main") or soup.find("article") or soup.body
    if main is None:
        return f"Error: Could not extract content from {url}."

    text = main.get_text(separator="\n", strip=True)

    # Clean up: remove excessive blank lines
    lines = [line for line in text.split("\n") if line.strip()]
    text = "\n".join(lines)

    # Truncate if too long
    if len(text) > MAX_CONTENT_LENGTH:
        logger.info("scrape_webpage: truncating", original_length=len(text))
        text = text[:MAX_CONTENT_LENGTH] + (
            "\n\n[... content truncated, use more specific URL for details ...]"
        )

    logger.info("scrape_webpage: success", url=url, text_length=len(text))
    return f"## Content from {url}\n\n{text}"


@tool
def search_and_scrape(query: str, num_results: int = 3) -> str:
    """Search the web and scrape the top results in one step.

    Performs a DuckDuckGo search and automatically scrapes the top pages
    to provide detailed information. Best for research questions.

    Args:
        query: The search query.
        num_results: Number of pages to scrape (1-5, default 3).

    Returns:
        Combined search results with scraped content from each page.
    """
    from assistant_bird.tools.web_search import web_search

    num_results = min(max(num_results, 1), 5)

    # Search first
    search_result = web_search.invoke({"query": query, "num_results": num_results})
    if "No results found" in search_result or "Search failed" in search_result:
        return search_result

    # Extract URLs from search results
    urls = []
    for line in search_result.split("\n"):
        if line.strip().startswith("URL:"):
            url = line.replace("URL:", "").strip()
            if url:
                urls.append(url)

    if not urls:
        return search_result

    # Scrape each URL
    parts = [search_result, "\n---\n## 📄 详细内容\n"]
    for i, url in enumerate(urls, 1):
        parts.append(f"\n### {i}. {url}")
        scraped = scrape_webpage.invoke({"url": url})
        # Truncate each scraped section
        if len(scraped) > 2000:
            scraped = scraped[:2000] + "\n...(truncated per page)"
        parts.append(scraped)

    return "\n".join(parts)
