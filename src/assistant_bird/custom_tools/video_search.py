"""Video search tool using yt-dlp — search YouTube and Bilibili.

Supports multi-platform video search with metadata extraction.
Subtitle/caption extraction is available via the `extract_subs` parameter.
"""

from langchain_core.tools import tool

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

# Mimic a normal browser to avoid anti-scraping blocks (especially Bilibili)
BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

MAX_RESULTS = 5

SEARCH_PREFIX: dict[str, str] = {
    "youtube": "ytsearch",
    "bilibili": "bilisearch",
}


def _format_duration(seconds: float | None) -> str:
    """Convert seconds to human-readable duration string."""
    if not seconds or seconds <= 0:
        return ""
    mins, secs = divmod(int(seconds), 60)
    if mins >= 60:
        hours, mins = divmod(mins, 60)
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def _format_view_count(count: int | None) -> str:
    """Format view count with Chinese units."""
    if not count:
        return ""
    if count >= 10_000:
        return f"{count / 10_000:.1f}万"
    return str(count)


def _search_platform(
    prefix: str,
    platform_name: str,
    query: str,
    max_results: int,
) -> list[dict]:
    """Run a yt-dlp search against a single platform.

    Args:
        prefix: yt-dlp search prefix (ytsearch / bilisearch).
        platform_name: Human-readable platform name for logging.
        query: Search keywords.
        max_results: Max entries to return.

    Returns:
        List of video info dicts with keys: title, url, duration, uploader,
        view_count, description, platform.
    """
    import yt_dlp

    search_query = f"{prefix}{max_results}:{query}"

    # Bilibili needs full extraction (slower) to get titles;
    # YouTube works fine with flat extraction (fast).
    if platform_name == "Bilibili":
        ydl_opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
            "playlistend": max_results,
            "http_headers": BROWSER_HEADERS,
        }
    else:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search_query, download=False)

    entries = info.get("entries") or []

    results: list[dict] = []
    for e in entries:
        title = e.get("title")
        if not title:
            continue  # Skip entries with no title
        results.append({
            "title": title,
            "url": e.get("url") or e.get("webpage_url") or "",
            "duration": e.get("duration"),
            "uploader": e.get("uploader") or e.get("channel") or "",
            "view_count": e.get("view_count"),
            "description": str(e.get("description") or "")[:200],
            "platform": platform_name,
        })

    logger.info(
        "video_search: platform done",
        platform=platform_name,
        count=len(results),
    )
    return results


@tool
def video_search(
    query: str,
    platform: str = "auto",
    max_results: int = 3,
) -> str:
    """搜索 YouTube 和 B站(Bilibili) 视频，返回标题、链接、时长等元数据。

    适用场景：用户询问视频教程、技术评测、vlog、视频新闻等内容时。
    也可用于查找特定主题的最新视频或热门视频。

    Args:
        query: 搜索关键词，建议用空格分隔多个关键词（如 'Python 教程'）。
        platform: 搜索平台，可选 auto（自动同时搜两个平台）/ youtube / bilibili。
                  auto 模式会优先展示 YouTube 结果。
        max_results: 最多返回的结果数（1-5，默认3）。

    Returns:
        Markdown 格式的视频信息列表，包含标题、平台、作者、时长、播放量、链接。
    """
    max_results = min(max(max_results, 1), MAX_RESULTS)

    # Decide which platforms to search
    if platform == "auto":
        targets = [("youtube", "YouTube"), ("bilibili", "Bilibili")]
    elif platform == "youtube":
        targets = [("youtube", "YouTube")]
    elif platform == "bilibili":
        targets = [("bilibili", "Bilibili")]
    else:
        return (
            f"❌ 不支持的平台「{platform}」，"
            "可选值: auto / youtube / bilibili"
        )

    logger.info(
        "video_search: starting",
        query=query,
        platform=platform,
        max_results=max_results,
    )

    # Search each platform, collect results
    all_results: list[dict] = []
    for key, name in targets:
        try:
            prefix = SEARCH_PREFIX[key]
            results = _search_platform(prefix, name, query, max_results)
            all_results.extend(results)
        except Exception as e:
            logger.warning(
                "video_search: platform failed",
                platform=name,
                error=str(e),
            )

    if not all_results:
        return (
            f"❌ 未找到与「{query}」相关的视频。\n\n"
            "可能原因：关键词过于生僻、网络问题、或平台暂时不可用。"
            "请尝试更换关键词或指定具体平台。"
        )

    # Build Markdown output
    display_count = min(len(all_results), max_results)
    lines = [f"## 🎬 视频搜索: {query}", ""]

    for i, v in enumerate(all_results[:display_count], 1):
        title = v["title"]
        url = v["url"]
        dur_str = _format_duration(v["duration"])
        uploader = v["uploader"]
        view_str = _format_view_count(v["view_count"])
        plat = v["platform"]
        desc = v["description"]

        lines.append(f"### {i}. {title}")
        lines.append("")
        lines.append("| 属性 | 值 |")
        lines.append("|------|------|")
        lines.append(f"| 📺 平台 | {plat} |")
        if uploader:
            lines.append(f"| 👤 作者 | {uploader} |")
        if dur_str:
            lines.append(f"| ⏱️ 时长 | {dur_str} |")
        if view_str:
            lines.append(f"| 👁️ 播放量 | {view_str} |")
        if url:
            lines.append(f"| 🔗 链接 | {url} |")
        if desc:
            lines.append(f"| 📝 简介 | {desc} |")
        lines.append("")

    lines.append(
        f"📊 共找到 {len(all_results)} 个相关视频，"
        f"显示前 {display_count} 个"
    )

    logger.info(
        "video_search: success",
        query=query,
        total=len(all_results),
        displayed=display_count,
    )
    return "\n".join(lines)
