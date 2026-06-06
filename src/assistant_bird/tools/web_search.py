"""DuckDuckGo web search tool with fast-fail fallback.

Two-phase approach (single attempt per phase, no retry spiraling):
1. Primary: duckduckgo_search library (DDGS) — fast, structured results
2. Fallback: Direct httpx → DuckDuckGo HTML endpoint — different code path

Both phases share the same host (DuckDuckGo). If that host is unreachable,
both fail fast (~10s total) and the tool returns an honest error message.
"""

import random
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

# ── Timeout config ───────────────────────────────────────────────────────────
# DDGS uses its own internal httpx client + impersonation library. The timeout
# parameter only controls httpx, not the impersonation setup. We wrap it with
# a Python-level ThreadPoolExecutor timeout as a hard backstop.
# IMPORTANT: ThreadPoolExecutor.__exit__ waits for threads — we use shutdown(wait=False)
# to avoid hanging on DDGS cleanup after the hard timeout fires.
DDGS_INTERNAL_TIMEOUT = 5
DDGS_HARD_TIMEOUT = 8  # Python-level kill — must be > internal
# Explicit per-phase timeouts for the HTML fallback.
# The `timeout` parameter caps the total request time (including DNS).
HTTP_TIMEOUT = httpx.Timeout(timeout=8.0, connect=4.0, read=6.0, write=3.0, pool=3.0)

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0"
    ),
]


def _search_via_ddgs(query: str, num_results: int) -> list[dict] | None:
    """Primary: use duckduckgo_search library with hard Python-level timeout.

    DDGS uses an impersonation library whose connection setup can exceed
    the httpx timeout. We wrap it in ThreadPoolExecutor to enforce a hard
    wall-clock timeout that the impersonation library cannot bypass.

    Uses shutdown(wait=False) to avoid executor cleanup blocking after
    a timeout — the orphaned thread is harmless and will die on its own.

    Returns list of {title, body, href} or None on failure.
    """
    def _call_ddgs() -> list[dict]:
        from duckduckgo_search import DDGS

        ddgs = DDGS(timeout=DDGS_INTERNAL_TIMEOUT)
        try:
            return list(ddgs.text(query, max_results=num_results))
        finally:
            ddgs.__exit__(None, None, None)

    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(_call_ddgs)
        results = future.result(timeout=DDGS_HARD_TIMEOUT)
    except FutureTimeout:
        logger.warning("web_search: DDGS hard timeout", query=query[:60])
        return None
    except Exception as e:
        logger.warning(
            "web_search: DDGS failed",
            query=query[:60],
            error=str(e)[:80],
        )
        return None
    finally:
        executor.shutdown(wait=False)  # Don't wait for orphaned DDGS cleanup

    if results:
        logger.info(
            "web_search: DDGS OK",
            query=query[:60],
            count=len(results),
        )
        return results
    logger.info("web_search: DDGS returned empty", query=query[:60])
    return None


async def _search_via_html(query: str, num_results: int) -> list[dict] | None:
    """Fallback: scrape DuckDuckGo HTML endpoint directly with httpx.

    Uses https://html.duckduckgo.com/html — the server-side rendered variant
    that doesn't require JavaScript. Different code path from DDGS, so it
    may succeed when DDGS's impersonation layer fails.

    Returns list of {title, body, href} or None on failure.
    """
    from urllib.parse import quote

    url = f"https://html.duckduckgo.com/html?q={quote(query)}"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
    except httpx.TimeoutException:
        logger.warning("web_search: HTML fallback timed out", query=query[:60])
        return None
    except Exception as e:
        logger.warning(
            "web_search: HTML fallback HTTP failed",
            query=query[:60],
            error=str(e)[:80],
        )
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    result_els = soup.select(".result")

    if not result_els:
        # Try lite endpoint as sub-fallback
        try:
            lite_url = f"https://lite.duckduckgo.com/lite/?q={quote(query)}"
            async with httpx.AsyncClient(
                timeout=HTTP_TIMEOUT, follow_redirects=True,
            ) as client:
                lite_resp = await client.get(lite_url, headers=headers)
                lite_resp.raise_for_status()
            lite_soup = BeautifulSoup(lite_resp.text, "html.parser")
            result_els = lite_soup.select("a.result-link")
        except Exception:
            pass

    if not result_els:
        logger.info("web_search: HTML fallback empty", query=query[:60])
        return None

    results: list[dict] = []
    for el in result_els[:num_results]:
        link_el = (
            el.select_one("a.result__a")
            or el.select_one("a.result-link")
            or el.find("a")
        )
        title = link_el.get_text(strip=True) if link_el else ""
        href = link_el.get("href", "") if link_el else ""

        # Decode DuckDuckGo redirect URLs
        if isinstance(href, str) and "uddg=" in href:
            from urllib.parse import parse_qs, urlparse
            parsed = urlparse(href)
            qs = parse_qs(parsed.query)
            href = qs.get("uddg", [href])[0]

        snippet_el = (
            el.select_one("a.result__snippet")
            or el.select_one(".result-snippet")
        )
        body = snippet_el.get_text(strip=True) if snippet_el else ""

        if title and len(title) > 3:
            results.append({"title": title, "body": body, "href": href})

    if results:
        logger.info(
            "web_search: HTML fallback OK",
            query=query[:60],
            count=len(results),
        )
        return results
    return None


def _format_results(query: str, results: list[dict]) -> str:
    """Format search results as Markdown."""
    lines = [f"## Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "No title")
        body = r.get("body", "No description")
        href = r.get("href", "")
        lines.append(f"{i}. **{title}**")
        lines.append(f"   {body}")
        if href:
            lines.append(f"   URL: {href}")
        lines.append("")
    return "\n".join(lines)


@tool
async def web_search(query: str, num_results: int = 5) -> str:
    """Search the web using DuckDuckGo and return formatted results.

    Uses a two-phase approach for reliability:
    1. Primary: DuckDuckGo instant answer API (fast, structured)
    2. Fallback: Direct HTML scraping (browser-like, different code path)

    Args:
        query: The search query string.
        num_results: Number of results to return (default 5, max 10).

    Returns:
        Formatted search results with titles, snippets, and URLs.
    """
    num_results = min(max(num_results, 1), 10)
    logger.info("web_search: searching", query=query[:80], num_results=num_results)

    # ── Phase 1: DDGS library ──
    results = _search_via_ddgs(query, num_results)
    if results:
        return _format_results(query, results)

    # ── Phase 2: HTML scraping fallback ──
    logger.info("web_search: DDGS failed, trying HTML fallback", query=query[:60])
    results = await _search_via_html(query, num_results)
    if results:
        return _format_results(query, results)

    # ── Both phases exhausted ──
    logger.error("web_search: all methods exhausted", query=query[:80])
    return (
        "⚠️ 搜索暂时不可用（DuckDuckGo 两种接入方式均已尝试，均失败）。\n\n"
        "这通常是因为当前网络环境无法访问 DuckDuckGo。\n"
        "该问题通常会在几分钟到几小时后自动恢复。\n\n"
        "**重要**: 请勿凭记忆编造搜索结果。诚实告知用户\n"
        "「搜索功能暂时不可用，建议稍后重试或使用其他搜索渠道」"
    )
