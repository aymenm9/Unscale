"""Quick filter: drop the clear misses before the expensive research step.

It uses decision models. A decision model does not write text: for each company it answers
one typed question, "keep, or which reason to drop?", with a probability for every option.
There is no JSON to parse or invent, and code makes the final call from the numbers.

Tried in order, per batch of companies:
1. Google's Gemini Decision 1 (Decisions API).
2. Cloudflare's Clef, if Gemini Decision fails (no key, daily limit, error).
3. A fast chat model that judges 10 companies per call, if both decision models fail.
If everything fails, everyone is kept. Unsure always means keep.
"""

import json

import httpx

from app.agents import llm
from app.agents.prompts import QUICK_FILTER
from app.agents.schemas import QuickFilterResult
from app.config import settings
from app.guards.research import align_quick_verdicts

BATCH = 10

# Drop only when the model is fairly sure it is NOT a fit. A wrong "no" loses a good company
# forever; a wrong "yes" only costs one more research step.
DROP_WHEN_KEEP_BELOW = 0.25

QUESTION = (
    "Is this company worth researching as a possible client of Ledgerwise (bookkeeping for "
    "US e-commerce brands) for this campaign? Pick the main reason."
)
# The options the model chooses from. The text is what the model reads; DROP_REASONS is what
# the sales team sees on a dropped company.
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


class DecisionFailed(Exception):
    pass


def fit_question() -> dict:
    return {"fit": {"type": "choice", "instructions": QUESTION, "criteria": OPTIONS}}


def read_fit_answer(answers: dict | None) -> dict:
    """Both APIs answer {"fit": {"choice": "keep", "probabilities": {...}, "confidence": ...}}."""
    answer = (answers or {}).get("fit")
    if not isinstance(answer, dict) or not isinstance(answer.get("probabilities"), dict):
        raise DecisionFailed("no answer")
    return answer


def post_json(url: str, body: dict, headers: dict) -> dict:
    try:
        res = httpx.post(url, json=body, headers=headers, timeout=30)
        data = res.json()
    except (httpx.HTTPError, ValueError) as e:
        raise DecisionFailed(str(e)) from e
    if res.status_code != 200:
        raise DecisionFailed(f"HTTP {res.status_code}: {str(data)[:200]}")
    return data


def ask_gemini_decision(campaign: dict, company: dict) -> dict:
    """One call to Google's Decisions API (POST /v1beta/decisions) for one company."""
    if not (settings.gemini_decision_model and settings.gemini_api_key):
        raise DecisionFailed("Gemini Decision is not configured")
    data = post_json(
        "https://generativelanguage.googleapis.com/v1beta/decisions",
        {
            "model": settings.gemini_decision_model,
            "input": json.dumps({"campaign": campaign, "company": company}),
            "questions": fit_question(),
        },
        {"x-goog-api-key": settings.gemini_api_key},
    )
    return read_fit_answer(data.get("answers"))


def ask_clef(campaign: dict, company: dict) -> dict:
    """One call to Cloudflare's Clef (Workers AI) for one company."""
    if not (settings.clef_model and settings.cloudflare_account_id and settings.cloudflare_api_key):
        raise DecisionFailed("Clef is not configured")
    data = post_json(
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{settings.cloudflare_account_id}/ai/run/@cf/cloudflare/{settings.clef_model}",
        {
            "model": settings.clef_model,
            "state": {"campaign": campaign, "company": company},
            "questions": fit_question(),
        },
        {"Authorization": f"Bearer {settings.cloudflare_api_key}"},
    )
    if not data.get("success"):
        raise DecisionFailed(str(data.get("errors"))[:200])
    return read_fit_answer((data.get("result") or {}).get("answers"))


def decide(answer: dict, model_name: str = "decision model") -> tuple[bool, str]:
    """Turn the probabilities into keep/drop plus a reason. Plain code, easy to test."""
    probs = answer["probabilities"]
    p_keep = float(probs.get("keep", 1.0))
    if p_keep >= DROP_WHEN_KEEP_BELOW:
        return True, f"{model_name}: worth researching ({p_keep:.0%} keep)."
    worst = max((k for k in probs if k in DROP_REASONS), key=lambda k: probs[k], default=None)
    if worst is None:
        return True, f"{model_name} gave no clear reason; kept to be safe."
    return False, f"{DROP_REASONS[worst]} ({model_name}, {probs[worst]:.0%} sure)."


def decision_batch(ask, model_name: str, campaign: dict, companies: list[dict]) -> dict:
    return {c["domain"]: decide(ask(campaign, c), model_name) for c in companies}


def llm_batch(campaign: dict, companies: list[dict]) -> dict[str, tuple[bool, str]]:
    """Last fallback: a chat model judges up to 10 companies in one call."""
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
    for ask, name in ((ask_gemini_decision, "Gemini Decision"), (ask_clef, "Clef")):
        try:
            return decision_batch(ask, name, campaign, companies)
        except DecisionFailed:
            continue
    return llm_batch(campaign, companies)


def run(campaign: dict, companies: list[dict]) -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}
    for i in range(0, len(companies), BATCH):
        out.update(filter_batch(campaign, companies[i : i + BATCH]))
    return out
