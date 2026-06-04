"""Web scraping tool using httpx + BeautifulSoup.

Anti-scraping protections: rotating User-Agent pool, browser-like headers,
random delay between requests, and exponential backoff on rate limits.
"""

import random
import time

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

TIMEOUT = 15.0
MAX_CONTENT_LENGTH = 8000

# Browser-grade User-Agent pool — rotated per request to avoid fingerprinting
USER_AGENTS = [
    # Chrome 125 on Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    # Safari 17.5 on macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"
    ),
    # Firefox 126 on Linux
    (
        "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0"
    ),
    # Edge 125 on Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0"
    ),
    # Chrome on macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
]

# Minimum delay between requests to the same domain (seconds)
_MIN_REQUEST_GAP = 0.5
_domain_last_request: dict[str, float] = {}


def _get_headers(referer: str = "https://www.google.com/") -> dict[str, str]:
    """Build a complete set of browser-like request headers."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": referer,
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
    }


def _rate_limit_domain(domain: str) -> None:
    """Enforce minimum request gap per domain to avoid triggering rate limits."""
    now = time.monotonic()
    last = _domain_last_request.get(domain, 0)
    gap = _MIN_REQUEST_GAP + random.uniform(0, 0.5)
    if now - last < gap:
        time.sleep(gap - (now - last))
    _domain_last_request[domain] = time.monotonic()


def _extract_domain(url: str) -> str:
    """Extract bare domain from a URL for rate-limit tracking."""
    try:
        return url.split("://", 1)[1].split("/", 1)[0].split("?")[0]
    except IndexError:
        return url


@tool
def scrape_webpage(url: str) -> str:
    """Fetch and extract text content from a web page.

    Strips out scripts, styles, navigation elements and returns clean text.
    Handles anti-scraping protections (403) and rate limits (429) gracefully.

    Args:
        url: The full URL to scrape (must start with http:// or https://).

    Returns:
        Extracted text content, truncated if very large.
    """
    if not url.startswith(("http://", "https://")):
        return f"Error: Invalid URL '{url}'. Must start with http:// or https://"

    domain = _extract_domain(url)
    _rate_limit_domain(domain)
    headers = _get_headers()

    logger.info("scrape_webpage: fetching", url=url[:100])

    max_attempts = 3
    last_error = ""

    for attempt in range(max_attempts):
        if attempt > 0:
            # Exponential backoff: 2s → 5s → 10s
            wait = 2.0 * (2 ** (attempt - 1)) + random.uniform(0, 1.0)
            logger.info(
                "scrape_webpage: retrying",
                url=url[:80],
                attempt=attempt + 1,
                wait=round(wait, 1),
            )
            time.sleep(wait)
            # Rotate User-Agent on retry
            headers["User-Agent"] = random.choice(USER_AGENTS)

        try:
            with httpx.Client(
                timeout=TIMEOUT,
                follow_redirects=True,
                http2=True,
            ) as client:
                response = client.get(url, headers=headers)
        except httpx.TimeoutException:
            last_error = f"Error: Request to {url} timed out after {TIMEOUT}s."
            continue
        except httpx.ConnectError:
            return f"Error: Could not connect to {url}. The site may be down."
        except Exception as e:
            last_error = f"Error fetching {url}: {str(e)}"
            continue

        status = response.status_code

        if status == 200:
            break
        elif status == 403:
            logger.warning(
                "scrape_webpage: 403 forbidden (anti-bot protection)",
                url=url[:80],
                attempt=attempt + 1,
            )
            last_error = (
                f"Error: {url} returned 403 Forbidden — "
                "the site is blocking automated access."
            )
            # For 403, try a different User-Agent next round
            continue
        elif status == 404:
            return (
                f"Error: Page not found (404) at {url}. "
                "The article may have moved or the URL may be incorrect. "
                "Try searching for the article by title instead."
            )
        elif status == 429:
            logger.warning(
                "scrape_webpage: 429 rate limited",
                url=url[:80],
                attempt=attempt + 1,
            )
            last_error = f"Rate limited (429) by {url}."
            continue
        elif status >= 500:
            last_error = f"Error: Server error ({status}) at {url}."
            continue
        else:
            return f"Error: Unexpected HTTP {status} from {url}."

    if "response" not in dir():  # noqa — all attempts failed
        return last_error or f"Error: Failed to fetch {url} after {max_attempts} attempts."

    # ── Parse response ──
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "text/plain" not in content_type:
        return (
            f"Error: URL returned non-text content type '{content_type}'. "
            "Cannot scrape binary files."
        )

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript", "header"]):
        tag.decompose()

    # Try main content area first, fall back to body
    main = soup.find("main") or soup.find("article") or soup.body
    if main is None:
        return f"Error: Could not extract content from {url}."

    text = main.get_text(separator="\n", strip=True)
    lines = [line for line in text.split("\n") if line.strip()]
    text = "\n".join(lines)

    if len(text) > MAX_CONTENT_LENGTH:
        logger.info("scrape_webpage: truncating", original_length=len(text))
        text = text[:MAX_CONTENT_LENGTH] + (
            "\n\n[... content truncated, use more specific URL for full article ...]"
        )

    logger.info("scrape_webpage: success", url=url[:80], text_length=len(text))
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

    parts = [search_result, "\n---\n## 📄 详细内容\n"]
    for i, url in enumerate(urls, 1):
        parts.append(f"\n### {i}. {url}")
        scraped = scrape_webpage.invoke({"url": url})
        if len(scraped) > 2000:
            scraped = scraped[:2000] + "\n...(truncated per page)"
        parts.append(scraped)

    return "\n".join(parts)
