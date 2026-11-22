"""Qualifier: judges a researched company. The LLM gives reasons; code gives the verdict."""

import json

from app.agents import llm
from app.agents.prompts import QUALIFIER
from app.agents.schemas import QualifyResult
from app.config import settings
from app.guards.research import drop_repeats, keep_cited, score_and_verdict, size_rule


def qualify(campaign: dict, name: str, evidence: list[dict]) -> dict:
    """evidence: [{id, claim, quote, url}]. Returns everything the DB row needs."""
    ev_text = "\n".join(f'[{e["id"]}] {e["claim"]} (quote: "{e["quote"]}")' for e in evidence)
    user = f"CAMPAIGN: {json.dumps(campaign)}\nCompany: {name}\n\nEVIDENCE:\n<page>\n{ev_text}\n</page>"
    r = llm.structured(QUALIFIER, user, QualifyResult, chain_names=settings.llm_judge)
    allowed = {e["id"] for e in evidence}
    reasons_for = drop_repeats(keep_cited([x for x in r.reasons_for if x.points > 0], allowed))
    reasons_against = keep_cited([x for x in r.reasons_against if x.points < 0], allowed)
    cap, cap_why = size_rule(r.revenue_band, r.revenue_confidence, r.staff_band, r.staff_confidence)
    if not reasons_for and cap > 40:  # nothing to write about and no sign they need help
        cap, cap_why = 40, "No sign yet that it needs bookkeeping help."
    size_known = r.revenue_band != "unknown" or r.staff_band != "unknown"
    score, verdict = score_and_verdict(
        reasons_for, reasons_against, r.confidence, settings.min_confidence, cap, size_known
    )
    summary = f"{cap_why} {r.summary}".strip() if cap < 100 else r.summary
    return {
        "score": score,
        "verdict": verdict,
        "reasons": [x.model_dump() for x in reasons_for + reasons_against],
        "confidence": r.confidence,
        "summary": summary,
        "revenue_band": r.revenue_band,
        "revenue_confidence": r.revenue_confidence,
        "staff_band": r.staff_band,
        "staff_confidence": r.staff_confidence,
    }
