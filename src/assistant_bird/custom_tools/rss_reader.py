"""RSS/Atom feed reader tool — parse any RSS or Atom feed to Markdown.

Uses feedparser for parsing and httpx for HTTP transport (already project deps).
No extra dependencies beyond the project baseline.
"""

import feedparser
import httpx
from langchain_core.tools import tool

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

TIMEOUT = 15.0
USER_AGENT = (
    "Mozilla/5.0 (compatible; AssistantBird/0.5; +https://github.com/lkk031/bird-assistant)"
)
MAX_ENTRIES = 20

def _fetch_feed_content(url: str) -> str:
    """Fetch feed XML via httpx with SSL fallback.

    Tries standard SSL first, then falls back to verify=False (many hosts
    have outdated or self-signed certs — public RSS data is not sensitive).
    """
    client_kwargs = {
        "timeout": TIMEOUT,
        "follow_redirects": True,
        "headers": {"User-Agent": USER_AGENT},
    }

    # Attempt 1: standard SSL
    try:
        with httpx.Client(**client_kwargs, verify=True) as client:  # type: ignore[arg-type]
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text
    except Exception:
        pass

    # Attempt 2: relaxed SSL
    with httpx.Client(**client_kwargs, verify=False) as client:  # type: ignore[arg-type]
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def _parse_date(entry: dict) -> str:
    """Extract the most useful date string from a feed entry."""
    for key in ("published", "updated", "created"):
        val = entry.get(key)
        if val:
            # Keep the first 25 chars (e.g. "Sat, 06 Jun 2026 01:32:09")
            return val[:25]
    return ""


def _clean_summary(text: str, max_len: int = 200) -> str:
    """Strip HTML tags and truncate summary text."""
    import re

    if not text:
        return ""
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", "", text)
    # Collapse whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > max_len:
        clean = clean[: max_len - 3] + "..."
    return clean


@tool
def rss_feed(url: str, limit: int = 10) -> str:
    """读取 RSS/Atom 订阅源，返回最新的文章列表。

    适用场景：订阅技术博客、播客、新闻源、学术论文等任意 RSS feed。
    用户说「订阅」「追踪」「看看最近更新」「RSS」「博客更新」时使用。

    Args:
        url: RSS/Atom 订阅源的完整 URL（如 https://hnrss.org/frontpage）。
             必须是 http:// 或 https:// 开头的合法 URL。
        limit: 返回的文章数量（1-20，默认10）。

    Returns:
        Markdown 格式的文章列表，包含标题、日期、摘要和链接。
    """
    limit = min(max(limit, 1), MAX_ENTRIES)

    if not url.startswith(("http://", "https://")):
        return f"❌ 无效的订阅源 URL「{url}」——必须以 http:// 或 https:// 开头。"

    logger.info("rss_feed: starting", url=url, limit=limit)

    # Fetch the feed content (with SSL fallback)
    try:
        raw_content = _fetch_feed_content(url)
    except httpx.TimeoutException:
        return f"❌ 读取订阅源超时（{TIMEOUT}秒）: {url}\n请稍后重试或检查 URL 是否正确。"
    except httpx.HTTPStatusError as e:
        return (
            f"❌ 订阅源返回 HTTP {e.response.status_code} 错误: {url}\n"
            "该源可能已失效或需要认证。"
        )
    except Exception as e:
        logger.error("rss_feed: HTTP request failed", url=url, error=str(e))
        return f"❌ 无法访问订阅源: {url}\n错误: {str(e)}"

    # Parse the feed
    feed = feedparser.parse(raw_content)
    entries = feed.entries

    if not entries:
        # Provide more specific hints
        feed_title = feed.feed.get("title", "")
        if feed_title:
            return (
                f"📡 **{feed_title}**\n\n"
                f"该订阅源当前没有文章。\n源地址: {url}"
            )
        return (
            f"❌ 无法解析订阅源「{url}」——该 URL 可能不是有效的 RSS/Atom feed。\n\n"
            "提示：RSS feed 的 URL 通常以 .xml 或 /rss 结尾，"
            "例如 https://hnrss.org/frontpage"
        )

    # Build output
    feed_title = feed.feed.get("title", "RSS 订阅")
    display_count = min(len(entries), limit)

    lines = [f"## 📡 {feed_title}", ""]

    for i, entry in enumerate(entries[:display_count], 1):
        title = entry.get("title", "无标题")
        link = entry.get("link", "")
        date_str = _parse_date(entry)
        summary = _clean_summary(
            entry.get("summary", entry.get("description", ""))
        )

        lines.append(f"### {i}. {title}")
        lines.append("")
        if date_str:
            lines.append(f"📅 {date_str}")
        if summary:
            lines.append("")
            lines.append(summary)
        if link:
            lines.append("")
            lines.append(f"🔗 {link}")
        lines.append("")

    lines.append("---")
    lines.append(
        f"📊 共 {len(entries)} 篇文章 · "
        f"订阅源: {url} · "
        f"显示前 {display_count} 篇"
    )

    logger.info(
        "rss_feed: success",
        url=url,
        total=len(entries),
        displayed=display_count,
    )
    return "\n".join(lines)
