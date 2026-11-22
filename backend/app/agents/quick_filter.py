"""Quick filter: a fast, cheap model (Gemini Flash Lite) says keep / drop for 10 companies at a time."""

import json

from app.agents import llm
from app.agents.prompts import QUICK_FILTER
from app.agents.schemas import QuickFilterResult
from app.config import settings
from app.guards.research import align_quick_verdicts

BATCH = 10


def filter_batch(campaign: dict, companies: list[dict]) -> dict[str, tuple[bool, str]]:
    """companies: [{domain, name, store, snippet}]. Returns {domain: (keep, reason)}."""
    domains = [c["domain"] for c in companies]
    user = (
        f"CAMPAIGN: {json.dumps(campaign)}\n\n<search_results>\n"
        + "\n".join(json.dumps(c) for c in companies)
        + "\n</search_results>"
    )
    try:
        result = llm.structured(
            QUICK_FILTER, user, QuickFilterResult, chain_names=settings.quick_filter_providers
        )
    except Exception:
        # The filter is only a shortcut: if it fails, keep everyone (unsure = keep).
        return {d: (True, "Quick filter unavailable; kept.") for d in domains}
    return align_quick_verdicts(domains, result.verdicts)


def run(campaign: dict, companies: list[dict]) -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}
    for i in range(0, len(companies), BATCH):
        out.update(filter_batch(campaign, companies[i : i + BATCH]))
    return out
