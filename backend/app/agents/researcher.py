"""Researcher: reads a brand's own pages (and one news search), extracts sourced facts.

Code fetches the pages; the LLM only reads them. Every quote is checked against the page.
"""

from app.agents import llm
from app.agents.prompts import RESEARCHER
from app.agents.schemas import ResearchResult
from app.config import settings
from app.guards.research import keep_sourced
from app.tools import web

# Common Shopify paths. Missing pages are skipped.
PATHS = [
    "",
    "/pages/about",
    "/pages/about-us",
    "/pages/our-story",
    "/pages/wholesale",
    "/pages/contact",
    "/pages/careers",
]
MAX_PAGES = 5


def fetch_pages(domain: str, name: str) -> dict[str, str]:
    """{url: text} for the pages we could read."""
    pages: dict[str, str] = {}
    for path in PATHS:
        if len(pages) >= MAX_PAGES:
            break
        url = f"https://{domain}{path}"
        text = web.read_page(url, max_chars=6000)
        if text and len(text) > 200:
            pages[url] = text
    try:
        for r in web.search(f'"{name}" news funding OR wholesale OR hiring', max_results=3):
            if domain not in r["url"] and r["snippet"]:
                pages[r["url"]] = f"{r['title']}\n{r['snippet']}"
    except web.SearchNotConfigured:
        pass
    return pages


def research(domain: str, name: str, store: dict | None) -> tuple[ResearchResult, list, dict]:
    """Returns (result with only verified facts, dropped facts with reasons, pages)."""
    pages = fetch_pages(domain, name)
    if not pages:
        return ResearchResult(summary="", channels=[], facts=[]), [], pages
    user = f"Company: {name} ({domain})\nStore data: {store}\n\n" + "\n\n".join(
        f'<page url="{url}">\n{text}\n</page>' for url, text in pages.items()
    )
    result = llm.structured(RESEARCHER, user, ResearchResult, chain_names=settings.llm_read)
    kept, dropped = keep_sourced(result.facts, pages)
    return result.model_copy(update={"facts": kept}), dropped, pages
