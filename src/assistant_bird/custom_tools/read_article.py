"""News article detail lookup — finds the real article and summarizes it.

Flow:
1. Search Google News RSS by article title → get Google News link
2. Extract the source domain from the RSS result
3. Use the Google News link (human-clickable) as primary URL
4. Return clickable link + AI-friendly context for summarization

The Google News link opens the full article preview on Google News, which is
useful for human reading. For AI summarization, the tool also provides the
article metadata and suggests the Agent use web_search for deeper scraping.
"""

import re
import xml.etree.ElementTree as ET

import httpx
from langchain_core.tools import tool

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

# Fine-grained timeout to prevent hanging on unresponsive servers
HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
USER_AGENT = (
    "Mozilla/5.0 (compatible; AssistantBird/0.1; +https://github.com/lkk031/bird-assistant)"
)


def _clean_html(raw: str) -> str:
    """Strip HTML tags and decode entities."""
    for entity, char in [
        ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
        ("&quot;", '"'), ("&#39;", "'"), ("&apos;", "'"),
    ]:
        raw = raw.replace(entity, char)
    return re.sub(r"<[^>]+>", "", raw)


@tool
def read_news_article(title: str) -> str:
    """Look up a news article by its title and return a clickable link plus details.

    Searches Google News RSS for the article, then returns:
    - A clickable Google News link (opens the full article preview)
    - The source/publisher name
    - Publication time
    - A short excerpt if available

    Use this when a user sees a headline in world_news results and wants to
    read the full article or get a summary. The returned URL can be clicked
    by the user, and the metadata helps the Agent provide context.

    Args:
        title: The article headline to look up. Use the exact title from
               world_news results for best matching.

    Returns:
        Article URL and metadata, or guidance if not found.
    """
    from urllib.parse import quote

    # Use main keywords from the title (first 8 words, avoid noise words)
    words = title.strip().split()
    query_words = [w for w in words[:12] if len(w) > 2 and w.lower()
                   not in ("the", "and", "for", "was", "are", "has", "had", "his")]
    query = " ".join(query_words[:8]) if query_words else title.strip()[:80]

    encoded = quote(query)
    url = (
        f"https://news.google.com/rss/search?"
        f"q={encoded}&hl=en-US&gl=US&ceid=US:en"
    )

    logger.info("read_news_article: searching", query=query[:80])

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
    except httpx.TimeoutException:
        return (
            "⚠️ 搜索文章超时（新闻源响应过慢）。\n\n"
            "请勿凭记忆编造文章内容。建议：\n"
            "1) 稍后重试\n"
            "2) 使用 web_search 搜索文章标题"
        )
    except httpx.HTTPStatusError as e:
        logger.warning(
            "read_news_article: HTTP error",
            status=e.response.status_code,
        )
        return (
            f"⚠️ 新闻源返回 HTTP {e.response.status_code}，暂时无法检索文章。\n\n"
            f"请勿凭记忆编造文章内容。建议使用 web_search 搜索标题。"
        )
    except Exception as e:
        logger.error("read_news_article: search failed", error=str(e)[:80])
        return (
            f"⚠️ 搜索文章时网络出错: {str(e)[:100]}\n\n"
            f"请勿凭记忆编造文章内容。使用 web_search 搜索标题可能更可靠。"
        )

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError:
        return (
            "⚠️ 新闻源返回格式异常（非 RSS/XML），搜索功能可能被限流。\n\n"
            "请勿凭记忆编造文章内容。建议使用 web_search 代替。"
        )

    # Find best matching item
    items = []
    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el = item.find("link")
        source_el = item.find("source")
        pubdate_el = item.find("pubDate")
        desc_el = item.find("description")

        item_title = _clean_html(title_el.text) if title_el is not None and title_el.text else ""
        item_link = link_el.text if link_el is not None and link_el.text else ""
        item_source = source_el.text if source_el is not None and source_el.text else ""
        item_date = pubdate_el.text if pubdate_el is not None and pubdate_el.text else ""
        item_desc = desc_el.text if desc_el is not None and desc_el.text else ""
        item_desc = _clean_html(item_desc).strip()
        # Remove duplicated title from description
        if item_desc.startswith(item_title):
            item_desc = item_desc[len(item_title):].strip()

        if not item_title or not item_link:
            continue

        items.append({
            "title": item_title,
            "link": item_link,
            "source": item_source,
            "date": item_date,
            "desc": item_desc,
        })

    if not items:
        return (
            f"⚠️ 未找到与「{title[:80]}」匹配的文章。\n\n"
            f"请勿凭记忆编造内容。建议：\n"
            f"1) 用更短的关键词重试（2-3 个核心词）\n"
            f"2) 使用 web_search 搜索完整标题\n"
            f"3) 告知用户当前无法获取该文章"
        )

    # Return top 3 matches (different sources often cover the same story)
    lines = ["## 📰 文章详情\n"]
    for i, item in enumerate(items[:3], 1):
        source = f" · {item['source']}" if item["source"] else ""
        date = f" · {item['date']}" if item["date"] else ""
        lines.append(f"### 结果 {i}")
        lines.append(f"**{item['title']}**")
        lines.append(f"🔗 {item['link']}{source}{date}")
        if item["desc"] and len(item["desc"]) > 20:
            lines.append(f"> {item['desc'][:300]}")
        lines.append("")

    lines.append(
        "---\n"
        "💡 **提示**：以上链接可在浏览器中打开阅读全文。"
        "如需 AI 总结文章内容，请用 `web_search` 搜索文中标题获取真实源 URL，"
        "然后用 `scrape_webpage` 抓取后我来总结。"
    )
    return "\n".join(lines)
