"""GitHub search tool — search repositories, issues, PRs, and code via REST API.

Uses the public GitHub REST API (api.github.com/search). No authentication
required for public content. Rate limit: ~10 req/min without token.
"""

import httpx
from langchain_core.tools import tool

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

BASE_URL = "https://api.github.com"
TIMEOUT = 15.0
USER_AGENT = (
    "Mozilla/5.0 (compatible; AssistantBird/0.5; +https://github.com/lkk031/bird-assistant)"
)
MAX_RESULTS = 10

# Map search types to API endpoints
SEARCH_ENDPOINTS: dict[str, str] = {
    "repositories": "/search/repositories",
    "issues": "/search/issues",
    "code": "/search/code",
}

# Human-readable labels for each type
TYPE_LABELS: dict[str, str] = {
    "repositories": "仓库",
    "issues": "Issue / PR",
    "code": "代码",
}


def _format_number(n: int) -> str:
    """Format large numbers to human-readable form."""
    if n >= 1000:
        return f"{n:,}"
    return str(n)


async def _search_github(
    search_type: str,
    query: str,
    max_results: int,
) -> list[dict]:
    """Call the GitHub Search REST API for a single search type.

    Args:
        search_type: One of 'repositories', 'issues', 'code'.
        query: Raw search query string.
        max_results: Max items to return.

    Returns:
        List of result dicts with uniform keys.
    """
    endpoint = SEARCH_ENDPOINTS[search_type]
    url = f"{BASE_URL}{endpoint}"

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(
            url,
            params={"q": query, "per_page": max_results},
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/vnd.github+json",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    items = data.get("items", [])
    results: list[dict] = []

    for item in items:
        if search_type == "repositories":
            results.append({
                "title": item.get("full_name", "?"),
                "url": item.get("html_url", ""),
                "subtitle": f"⭐ {_format_number(item.get('stargazers_count', 0))}",
                "extra": (
                    f"🍴 {_format_number(item.get('forks_count', 0))} · "
                    f"📝 {item.get('language', 'N/A') or 'N/A'} · "
                    f"🕐 {str(item.get('updated_at', ''))[:10]}"
                ),
                "description": str(item.get("description") or "")[:200],
            })
        elif search_type == "issues":
            state = item.get("state", "?")
            state_emoji = "🟢" if state == "open" else "🟣"
            is_pr = "pull_request" in item
            kind = "PR" if is_pr else "Issue"
            repo_url = item.get("repository_url", "")
            repo_name = (
                repo_url.replace("https://api.github.com/repos/", "")
                if repo_url
                else "?"
            )
            results.append({
                "title": item.get("title", "?"),
                "url": item.get("html_url", ""),
                "subtitle": f"{state_emoji} {state} {kind} · {repo_name}",
                "extra": (
                    f"💬 {item.get('comments', 0)} comments · "
                    f"👤 {item.get('user', {}).get('login', '?')} · "
                    f"🕐 {str(item.get('updated_at', ''))[:10]}"
                ),
                "description": str(item.get("body") or "")[:200],
            })
        elif search_type == "code":
            repo = item.get("repository", {})
            results.append({
                "title": item.get("name", item.get("path", "?")),
                "url": item.get("html_url", ""),
                "subtitle": (
                    f"📂 {repo.get('full_name', '?')} · "
                    f"{item.get('path', '?')}"
                ),
                "extra": "",
                "description": "",
            })

    return results


@tool
async def github_search(
    query: str,
    search_type: str = "repositories",
    max_results: int = 5,
) -> str:
    """在 GitHub 上搜索开源代码仓库、Issues、Pull Request 或代码内容。

    适用场景：查找开源项目、了解技术栈的流行框架、搜索特定代码示例、
    跟踪项目的 Issue/PR 讨论。

    支持 GitHub 搜索限定符：
    - language:python  → 限定语言
    - stars:>100       → 最低 star 数
    - org:langchain-ai → 限定组织
    - 多个条件用空格组合，如 'RAG framework language:python stars:>100'

    Args:
        query: 搜索关键词，支持 GitHub 高级搜索语法。
        search_type: 搜索类型 — repositories（仓库）/ issues（Issue和PR）/ code（代码）。
                     默认 repositories。
        max_results: 最多返回的结果数（1-10，默认5）。

    Returns:
        Markdown 格式的搜索结果列表。
    """
    max_results = min(max(max_results, 1), MAX_RESULTS)
    if search_type not in SEARCH_ENDPOINTS:
        return (
            f"❌ 不支持的搜索类型「{search_type}」，"
            "可选值: repositories / issues / code"
        )

    if not query.strip():
        return "❌ 搜索关键词不能为空。"

    label = TYPE_LABELS[search_type]
    logger.info(
        "github_search: starting",
        query=query,
        search_type=search_type,
        max_results=max_results,
    )

    try:
        items = await _search_github(search_type, query, max_results)
    except httpx.TimeoutException:
        return f"❌ GitHub 搜索超时（{TIMEOUT}秒），请稍后重试。"
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return (
                "❌ GitHub 代码搜索需要认证 Token。\n\n"
                "仓库和 Issue 搜索无需 Token 即可使用。"
                "如需搜索代码，请在 .env 中设置 GITHUB_TOKEN\n"
                "（GitHub Settings → Developer settings → Personal Access Token）。"
            )
        if e.response.status_code == 403:
            return (
                "❌ GitHub API 速率限制已用完（10次/分钟）。\n"
                "请稍等一分钟后再试，或提供 GitHub Token 提升限制。"
            )
        return (
            f"❌ GitHub API 返回 HTTP {e.response.status_code} 错误。\n"
            "请稍后重试。"
        )
    except Exception as e:
        logger.error("github_search: API request failed", error=str(e))
        return f"❌ GitHub 搜索失败: {str(e)}"

    if not items:
        return (
            f"## 🔍 GitHub {label}搜索: {query}\n\n"
            "未找到匹配结果。请尝试更换关键词或放宽条件。\n\n"
            "提示：GitHub 搜索对中文支持有限，建议使用英文关键词。"
        )

    # Build Markdown output
    display_count = min(len(items), max_results)
    lines = [f"## 🔍 GitHub {label}搜索: {query}", ""]

    for i, item in enumerate(items[:display_count], 1):
        title = item["title"]
        url = item["url"]
        subtitle = item["subtitle"]
        extra = item["extra"]
        desc = item["description"]

        lines.append(f"### {i}. {title}")
        lines.append("")
        lines.append(f"{subtitle}")
        if extra:
            lines.append(f"{extra}")
        if desc:
            # Clean up issue/PR body: strip markdown and truncate gaps
            clean_desc = desc.replace("\r", " ").replace("\n", " ")[:200]
            lines.append("")
            lines.append(f"> {clean_desc}")
        if url:
            lines.append("")
            lines.append(f"🔗 {url}")
        lines.append("")

    lines.append("---")
    lines.append(
        f"📊 匹配 {len(items)}+ 条结果 · "
        f"搜索类型: {label} · "
        f"显示前 {display_count} 条"
    )

    logger.info(
        "github_search: success",
        query=query,
        search_type=search_type,
        result_count=len(items),
    )
    return "\n".join(lines)
