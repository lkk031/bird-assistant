"""GitHub Trending repositories scraper tool.

Scrapes https://github.com/trending to discover hot projects, supporting
language filter and time range (daily/weekly/monthly).
"""

import re

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

BASE_URL = "https://github.com/trending"
TIMEOUT = 15.0
USER_AGENT = (
    "Mozilla/5.0 (compatible; AssistantBird/0.1; +https://github.com/lkk031/bird-assistant)"
)

# Supported languages (GitHub trending URL slugs)
SUPPORTED_LANGUAGES = {
    "python", "javascript", "typescript", "go", "rust", "java", "c", "c++", "c#",
    "ruby", "swift", "kotlin", "php", "vue", "css", "html", "shell", "scala",
    "dart", "lua", "julia", "r", "haskell", "elixir", "clojure", "erlang",
    "zig", "nim", "crystal", "ocaml", "matlab", "objective-c", "assembly",
    "powershell", "groovy", "perl", "coffeescript", "haxe", "racket", "vba",
    "jupyter notebook", "mdx", "tex", "liquid", "scss", "sass", "less",
    "makefile", "dockerfile", "cmake", "batchfile",
}


def _parse_stars_today(text: str) -> str:
    """Extract 'stars today/this week/this month' from free text."""
    m = re.search(r'[\d,]+ stars? (today|this week|this month)', text, re.IGNORECASE)
    return m.group(0) if m else ""


@tool
async def github_trending(
    language: str = "",
    since: str = "daily",
    max_results: int = 10,
) -> str:
    """Get GitHub trending repositories.

    Scrapes the GitHub trending page to discover today's hot open-source projects.
    Supports optional language filtering and time range selection.

    Args:
        language: Filter by programming language (e.g. 'python', 'rust', 'go').
                  Leave empty for all languages.
        since: Time range — 'daily' (today), 'weekly' (this week), or 'monthly'.
               Default is 'daily'.
        max_results: Number of trending repos to return (1-25, default 10).

    Returns:
        Formatted list of trending repositories with name, description, language,
        total stars, forks, and stars gained during the period.
    """
    max_results = min(max(max_results, 1), 25)
    if since not in ("daily", "weekly", "monthly"):
        since = "daily"

    # Build URL
    lang_slug = language.lower().strip().replace(" ", "-").replace("#", "-sharp")
    if lang_slug and lang_slug not in _normalize_lang_map():
        if lang_slug not in SUPPORTED_LANGUAGES:
            logger.warning(
                "github_trending: unknown language, using all",
                language=language,
            )
            lang_slug = ""

    if lang_slug:
        url = f"{BASE_URL}/{lang_slug}?since={since}"
    else:
        url = f"{BASE_URL}?since={since}"

    logger.info("github_trending: fetching", url=url, max_results=max_results)

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
    except httpx.TimeoutException:
        return "Error: GitHub trending request timed out. Please try again."
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} when fetching GitHub trending."
    except Exception as e:
        return f"Error fetching GitHub trending: {str(e)}"

    soup = BeautifulSoup(response.text, "html.parser")

    # Find all repo article cards
    articles = soup.find_all("article", class_="Box-row")
    if not articles:
        return "Error: Could not parse GitHub trending page. The page structure may have changed."

    results = []
    header = "## 🔥 GitHub Trending"
    if language:
        header += f" — {language.title()}"
    header += f" ({since})\n"
    results.append(header)

    count = 0
    for article in articles:
        if count >= max_results:
            break

        # Extract repo owner/name from h2 > a
        h2 = article.find("h2", class_="h3 lh-condensed")
        if not h2:
            continue
        repo_link = h2.find("a")
        if not repo_link:
            continue

        full_name = repo_link.get_text(strip=True)
        # full_name looks like "owner / repo"
        parts = [p.strip() for p in full_name.split("/")]
        if len(parts) != 2:
            continue
        owner, repo = parts
        repo_url = "https://github.com" + repo_link.get("href", "")

        # Description — in the <p> tag after h2
        desc_p = article.find("p", class_=re.compile(r"col-9|my-1"))
        description = ""
        if desc_p:
            # Remove the "owner / repo" text from the beginning
            desc_text = desc_p.get_text(separator=" ", strip=True)
            # Find and remove leading "owner / repo"
            if full_name in desc_text:
                desc_text = desc_text.split(full_name, 1)[-1].strip()
            description = desc_text

        # Programming language
        lang_span = article.find("span", itemprop="programmingLanguage")
        lang = lang_span.get_text(strip=True) if lang_span else ""

        # Stars (total) — link ending in /stargazers
        stars_total = ""
        stargazers_link = article.find("a", href=re.compile(r"/stargazers$"))
        if stargazers_link:
            stars_total = stargazers_link.get_text(strip=True)

        # Forks — link ending in /forks
        forks = ""
        forks_link = article.find("a", href=re.compile(r"/forks$"))
        if forks_link:
            forks = forks_link.get_text(strip=True)

        # Stars gained today/week/month
        stars_today = ""
        today_span = article.find("span", class_="d-inline-block float-sm-right")
        if today_span:
            stars_today = _parse_stars_today(today_span.get_text(" ", strip=True))

        # Format this repo
        count += 1
        line = f"\n{count}. **[{owner}/{repo}]({repo_url})**"
        if lang:
            line += f" · {lang}"
        line += f"\n   ⭐ {stars_total} total"
        if forks:
            line += f" · 🍴 {forks}"
        if stars_today:
            line += f" · 📈 {stars_today}"
        if description:
            line += f"\n   > {description[:200]}"
        results.append(line)

    if count == 0:
        results.append("\n_(No trending repositories found)_")

    results.append(f"\n---\n📊 Source: [{url}]({url})")
    return "\n".join(results)


def _normalize_lang_map() -> dict[str, str]:
    """Map common language name variants to GitHub trending slugs."""
    return {
        "c++": "c++",
        "cpp": "c++",
        "c#": "c#",
        "csharp": "c#",
        "objective-c": "objective-c",
        "objc": "objective-c",
        "jupyter": "jupyter notebook",
        "jupyter-notebook": "jupyter notebook",
    }
