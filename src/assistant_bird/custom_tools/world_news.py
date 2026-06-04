"""World news tool — multi-source global news aggregation.

Fetches headlines from multiple sources in parallel to avoid single-source bias:
- Aggregators: Google News (broad coverage, algorithmic)
- Direct sources: BBC World, NYT World, NPR, Al Jazeera, The Guardian

Topic search uses Google News RSS search (the only free searchable news API).

All sources are free RSS feeds — no API keys, no rate limits.
"""

import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

import httpx
from langchain_core.tools import tool

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

TIMEOUT = 15.0
USER_AGENT = (
    "Mozilla/5.0 (compatible; AssistantBird/0.1; +https://github.com/lkk031/bird-assistant)"
)

# ── News sources ───────────────────────────────────────────────────────────
# Each source has a name, RSS URL, and language.
# "aggregator" type = algorithmic (Google/Bing), "direct" type = editorial.

NEWS_SOURCES = [
    # Aggregators
    {
        "name": "Google News",
        "url": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
        "lang": "en",
        "source_type": "aggregator",
    },
    # Direct sources — diverse editorial perspectives
    {
        "name": "BBC World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "lang": "en",
        "source_type": "direct",
    },
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "lang": "en",
        "source_type": "direct",
    },
    {
        "name": "The Guardian",
        "url": "https://www.theguardian.com/world/rss",
        "lang": "en",
        "source_type": "direct",
    },
]

# Region-specific sources
REGION_SOURCES = {
    "china": [
        {
            "name": "Google News 中国",
            "url": "https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
            "lang": "zh",
            "source_type": "aggregator",
        },
    ],
    "us": [
        {
            "name": "NPR",
            "url": "https://feeds.npr.org/1001/rss.xml",
            "lang": "en",
            "source_type": "direct",
        },
        {
            "name": "NYT World",
            "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
            "lang": "en",
            "source_type": "direct",
        },
    ],
    "uk": [
        {
            "name": "BBC World",
            "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
            "lang": "en",
            "source_type": "direct",
        },
        {
            "name": "The Guardian",
            "url": "https://www.theguardian.com/world/rss",
            "lang": "en",
            "source_type": "direct",
        },
    ],
}

TOPIC_FEEDS = {
    "tech": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en",
    "business": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en",
    "science": "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=en-US&gl=US&ceid=US:en",
}

REGION_LABELS = {
    "china": "中国", "us": "美国", "uk": "英国", "world": "国际",
    "japan": "日本", "korea": "韩国", "tech": "科技",
    "business": "商业", "science": "科学",
}


def _clean_html(raw: str) -> str:
    """Strip HTML tags and decode entities."""
    for entity, char in [
        ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
        ("&quot;", '"'), ("&#39;", "'"), ("&apos;", "'"),
    ]:
        raw = raw.replace(entity, char)
    return re.sub(r"<[^>]+>", "", raw)


def _fetch_one_feed(source: dict, max_items: int) -> list[dict]:
    """Fetch and parse a single RSS feed.

    Returns list of {title, url, source_name, source_type, published}.
    URLs from direct sources (BBC, Guardian) are real article links.
    URLs from aggregators (Google News) are human-clickable preview pages.
    """
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            response = client.get(
                source["url"],
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
    except Exception as e:
        logger.warning(
            "world_news: feed failed",
            source=source["name"],
            error=str(e)[:80],
        )
        return []

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError:
        return []

    channel = root.find("channel")
    if channel is None:
        # Atom feed fallback
        return _parse_atom_feed(root, source, max_items)

    items = []
    for item in channel.findall("item"):
        if len(items) >= max_items:
            break

        title_el = item.find("title")
        link_el = item.find("link")
        pubdate_el = item.find("pubDate")

        title = _clean_html(title_el.text) if title_el is not None and title_el.text else ""
        article_url = link_el.text.strip() if link_el is not None and link_el.text else ""
        pubdate = pubdate_el.text if pubdate_el is not None and pubdate_el.text else ""

        if not title or len(title) < 10:
            continue

        items.append({
            "title": title,
            "url": article_url,
            "source_name": source["name"],
            "source_type": source["source_type"],
            "published": pubdate,
        })

    return items


def _parse_atom_feed(root, source: dict, max_items: int) -> list[dict]:
    """Parse Atom format feeds (used by some sources)."""
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []
    for entry in root.findall("atom:entry", ns):
        if len(items) >= max_items:
            break
        title_el = entry.find("atom:title", ns)
        updated_el = entry.find("atom:updated", ns)

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        pubdate = updated_el.text if updated_el is not None and updated_el.text else ""

        if not title or len(title) < 10:
            continue

        items.append({
            "title": title,
            "url": "",
            "source_name": source["name"],
            "source_type": source["source_type"],
            "published": pubdate,
        })
    return items


def _title_similar(a: str, b: str) -> bool:
    """Duplicate detection: two headlines are duplicates only if their
    significant words overlap very heavily AND the titles are short-moderate.
    Long titles with partial overlap = different angles on same topic → keep.
    """
    # Fast path: if first 30 chars (after lowercasing) are nearly identical
    a_start = re.sub(r"[^a-z0-9]", "", a.lower())[:30]
    b_start = re.sub(r"[^a-z0-9]", "", b.lower())[:30]
    if a_start == b_start:
        return True

    # Word overlap check — only for short titles where overlap means duplicate
    words_a = set(re.findall(r"\w{4,}", a.lower()))
    words_b = set(re.findall(r"\w{4,}", b.lower()))
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b)
    # Need 75%+ overlap AND at least 5 shared words to count as duplicate
    min_size = min(len(words_a), len(words_b))
    return overlap >= 5 and overlap >= min_size * 0.75


def _deduplicate(items: list[dict]) -> list[dict]:
    """Remove near-duplicate headlines across sources."""
    result = []
    for item in items:
        is_dup = any(_title_similar(item["title"], r["title"]) for r in result)
        if not is_dup:
            result.append(item)
    return result


def _fetch_headlines(sources: list[dict], max_results: int) -> tuple[list[dict], list[str]]:
    """Fetch headlines from multiple sources in parallel, deduplicate, return top N.

    Returns (items, all_source_names) where all_source_names includes ALL fetched
    sources (even those whose items were deduplicated away).
    """
    all_items = []

    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = {
            executor.submit(_fetch_one_feed, src, max_results): src
            for src in sources
        }
        for future in as_completed(futures):
            try:
                items = future.result()
                if items:
                    logger.info(
                        "world_news: source OK",
                        source=futures[future]["name"],
                        count=len(items),
                    )
                all_items.extend(items)
            except Exception as e:
                logger.warning(
                    "world_news: source error",
                    source=futures[future]["name"],
                    error=str(e)[:80],
                )

    # Track all source names BEFORE dedup
    all_source_names = list(dict.fromkeys(
        i["source_name"] for i in all_items
    ))

    # Deduplicate and interleave sources for diversity
    unique = _deduplicate(all_items)
    aggregator_items = [i for i in unique if i["source_type"] == "aggregator"]
    direct_items = [i for i in unique if i["source_type"] == "direct"]
    interleaved = []
    max_len = max(len(aggregator_items), len(direct_items))
    for i in range(max_len):
        if i < len(aggregator_items):
            interleaved.append(aggregator_items[i])
        if i < len(direct_items):
            interleaved.append(direct_items[i])

    return interleaved[:max_results], all_source_names


@tool
def world_news(
    topic: str = "",
    region: str = "world",
    max_results: int = 15,
) -> str:
    """Get recent world news headlines from multiple sources.

    Headlines mode (no topic): Fetches from Google News + BBC + Al Jazeera +
    The Guardian + NPR/NYT (by region). Results are merged and deduplicated
    to provide diverse perspectives.

    Topic search mode: Uses Google News RSS search to find articles
    matching your keywords.

    Shows titles, sources, and times. Does not include article URLs (RSS
    feeds use redirect links). To read a full article, tell me the title
    and I'll search for the real URL with web_search.

    Args:
        topic: Search keywords. Leave empty for top headlines.
               Examples: 'AI regulation', 'climate', 'stock market'.
        region: Headlines region — 'china', 'us', 'uk', 'world',
                'tech', 'business', 'science'. Default 'world'.
        max_results: Number of articles (1-25, default 15).

    Returns:
        Formatted, multi-source news list.
    """
    max_results = min(max(max_results, 1), 25)
    region_label = REGION_LABELS.get(region, region)

    if not topic or not topic.strip():
        # ── Headlines: multi-source aggregation ──
        if region in TOPIC_FEEDS:
            sources = [{
                "name": f"Google News {region_label}",
                "url": TOPIC_FEEDS[region],
                "lang": "en",
                "source_type": "aggregator",
            }]
        else:
            # Combine global sources + region-specific sources
            sources = list(NEWS_SOURCES)
            extra = REGION_SOURCES.get(region, [])
            sources.extend(extra)

        items, all_sources = _fetch_headlines(sources, max_results)

        if not items:
            return f"无法获取 {region_label} 新闻头条，请稍后重试。"

        now = datetime.now(UTC)
        src_names = list(dict.fromkeys(all_sources))
        lines = [
            f"## 🌍 {region_label}新闻头条",
            f"（{now.strftime('%Y-%m-%d %H:%M UTC')} · {len(src_names)} 个来源）",
            "",
            "> 💡 多源聚合，避免单一视角。点击链接阅读全文。"
            "想看 AI 总结？用 `read_news_article` 查找。",
            "",
        ]
        for i, item in enumerate(items, 1):
            pub = f" · {item['published']}" if item["published"] else ""
            url = item.get("url", "")
            is_direct = item.get("source_type") == "direct"
            url_label = "🔗 原文" if is_direct else "🔗 阅读"

            lines.append(f"{i}. **{item['title']}**")
            lines.append(f"   📰 {item['source_name']}{pub}")
            if url:
                lines.append(f"   [{url_label}]({url})")
            lines.append("")

        lines.append(f"📊 共 {len(items)} 条 · 来源: {', '.join(src_names)}")
        return "\n".join(lines)

    else:
        # ── Topic search: Google News RSS ──
        from urllib.parse import quote

        encoded = quote(topic.strip())
        url = (
            f"https://news.google.com/rss/search?"
            f"q={encoded}&hl=en-US&gl=US&ceid=US:en"
        )
        source = {"name": "Google News", "url": url, "lang": "en", "source_type": "aggregator"}
        items = _fetch_one_feed(source, max_results)

        if not items:
            return (
                f"未找到关于「{topic}」的新闻。试试缩短关键词。"
            )

        lines = [f"## 📰 新闻搜索: {topic.strip()}", ""]
        for i, item in enumerate(items, 1):
            pub = f" · {item['published']}" if item["published"] else ""
            url = item.get("url", "")
            is_direct = item.get("source_type") == "direct"
            url_label = "🔗 原文" if is_direct else "🔗 阅读"

            lines.append(f"{i}. **{item['title']}**")
            lines.append(f"   📰 {item['source_name']}{pub}")
            if url:
                lines.append(f"   [{url_label}]({url})")
            lines.append("")

        lines.append(f"📊 共 {len(items)} 条 · 来源: Google News")
        return "\n".join(lines)
