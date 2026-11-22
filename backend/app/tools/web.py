"""Web search (Tavily) and page reading (Jina Reader, then plain HTML as a fallback)."""

import html
import re

from app.config import settings
from app.tools import http

_search_cache: dict[str, list[dict]] = {}


class SearchNotConfigured(Exception):
    pass


def search(query: str, max_results: int = 8) -> list[dict]:
    """Tavily basic search: 1 credit. Returns [{title, url, snippet}]."""
    if not settings.tavily_api_key:
        raise SearchNotConfigured("TAVILY_API_KEY is not set")
    if query in _search_cache:
        return _search_cache[query]
    data = http.post_json(
        "https://api.tavily.com/search",
        {"query": query, "max_results": max_results, "search_depth": "basic"},
        {"Authorization": f"Bearer {settings.tavily_api_key}"},
    )
    results = [
        {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")}
        for r in data.get("results", [])
    ]
    _search_cache[query] = results
    return results


def _html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", raw)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def read_page(url: str, max_chars: int = 8000) -> str | None:
    """Readable text of a page, or None if it does not exist / cannot be read."""
    headers = {"Authorization": f"Bearer {settings.jina_api_key}"} if settings.jina_api_key else {}
    try:
        status, text = http.get(f"https://r.jina.ai/{url}", headers=headers, check_robots=False)
        if status == 200 and text.strip() and "404" not in text[:200]:
            return text[:max_chars]
        status, raw = http.get(url)
    except http.Blocked:
        return None
    if status != 200 or not raw:
        return None
    return _html_to_text(raw)[:max_chars]
