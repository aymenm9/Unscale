"""Quick filter: drop the clear misses before the expensive research step.

Step 1, Cloudflare Clef (a decision model): for each company it answers one typed question,
"keep, or which reason to drop?", with a probability for every option. It does not write
text, so there is no JSON to parse or invent. Code makes the final call from the numbers.
Step 2, if Clef fails (no key, daily limit, error): a fast chat model judges 10 at a time.
If both fail, everyone is kept. Unsure always means keep.
"""

import json

import httpx

from app.agents import llm
from app.agents.prompts import QUICK_FILTER
from app.agents.schemas import QuickFilterResult
from app.config import settings
from app.guards.research import align_quick_verdicts

BATCH = 10

# Drop only when Clef is fairly sure it is NOT a fit. A wrong "no" loses a good company
# forever; a wrong "yes" only costs one more research step.
DROP_WHEN_KEEP_BELOW = 0.25

# The options Clef chooses from. The text is what Clef reads; the reason is what the sales
# team sees on a dropped company.
OPTIONS = {
    "keep": "A US brand that sells its own physical products online and could fit, "
    "or the data is too thin to tell.",
    "not_a_store": "Not a brand selling its own products: an agency, software, marketplace, "
    "retailer of other brands, blog or listicle.",
    "too_big": "Clearly a large national brand or household name, far over $10M revenue "
    "or 50 staff.",
    "outside_us": "Clearly based outside the United States.",
    "wrong_category": "Sells something outside the campaign's categories.",
}
DROP_REASONS = {
    "not_a_store": "Not a brand selling its own products",
    "too_big": "Too big: a large national brand",
    "outside_us": "Based outside the US",
    "wrong_category": "Outside the campaign's categories",
}


class ClefFailed(Exception):
    pass


def ask_clef(campaign: dict, company: dict) -> dict:
    """One Clef call for one company. Returns the 'fit' answer:
    {"choice": "keep", "probabilities": {"keep": 0.9, ...}, "confidence": 0.8}"""
    if not (
        settings.decision_model and settings.cloudflare_account_id and settings.cloudflare_api_key
    ):
        raise ClefFailed("Clef is not configured")
    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{settings.cloudflare_account_id}/ai/run/@cf/cloudflare/{settings.decision_model}"
    )
    body = {
        "model": settings.decision_model,
        "state": {"campaign": campaign, "company": company},
        "questions": {
            "fit": {
                "type": "choice",
                "instructions": "Is this company worth researching as a possible client of "
                "Ledgerwise (bookkeeping for US e-commerce brands) for this campaign? "
                "Pick the main reason.",
                "criteria": OPTIONS,
            }
        },
    }
    try:
        res = httpx.post(
            url,
            json=body,
            headers={"Authorization": f"Bearer {settings.cloudflare_api_key}"},
            timeout=30,
        )
        data = res.json()
    except (httpx.HTTPError, ValueError) as e:
        raise ClefFailed(str(e)) from e
    if not data.get("success"):
        raise ClefFailed(str(data.get("errors"))[:200])
    answer = (data.get("result") or {}).get("answers", {}).get("fit")
    if not isinstance(answer, dict) or not isinstance(answer.get("probabilities"), dict):
        raise ClefFailed("Clef returned no answer")
    return answer


def decide(answer: dict) -> tuple[bool, str]:
    """Turn Clef's probabilities into keep/drop plus a reason. Plain code, easy to test."""
    probs = answer["probabilities"]
    p_keep = float(probs.get("keep", 1.0))
    if p_keep >= DROP_WHEN_KEEP_BELOW:
        return True, f"Decision model: worth researching ({p_keep:.0%} keep)."
    worst = max((k for k in probs if k in DROP_REASONS), key=lambda k: probs[k], default=None)
    if worst is None:
        return True, "Decision model gave no clear reason; kept to be safe."
    return False, f"{DROP_REASONS[worst]} (decision model, {probs[worst]:.0%} sure)."


def clef_batch(campaign: dict, companies: list[dict]) -> dict[str, tuple[bool, str]]:
    return {c["domain"]: decide(ask_clef(campaign, c)) for c in companies}


def llm_batch(campaign: dict, companies: list[dict]) -> dict[str, tuple[bool, str]]:
    """Fallback: a chat model judges up to 10 companies in one call."""
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


def filter_batch(campaign: dict, companies: list[dict]) -> dict[str, tuple[bool, str]]:
    """companies: [{domain, name, store, snippet}]. Returns {domain: (keep, reason)}."""
    try:
        return clef_batch(campaign, companies)
    except ClefFailed:
        return llm_batch(campaign, companies)


def run(campaign: dict, companies: list[dict]) -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}
    for i in range(0, len(companies), BATCH):
        out.update(filter_batch(campaign, companies[i : i + BATCH]))
    return out
