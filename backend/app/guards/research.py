"""Checks on what the find-companies agents return. Plain Python, no LLM.

Rule 2 of the brief: no fact without a source. Here that means a quote must really be on
the page we fetched, and every qualifier reason must cite evidence we stored.
"""

import re
from dataclasses import dataclass, field

from app.agents.schemas import Fact, Person, QuickVerdict, Reason

MIN_QUOTE_CHARS = 12


def _normalize(text: str) -> str:
    """Lowercase, straight quotes, single spaces. Pages and LLM quotes differ on these."""
    text = text.lower()
    for curly, straight in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"')):
        text = text.replace(curly, straight)
    text = text.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def quote_on_page(quote: str, page_text: str) -> bool:
    q = _normalize(quote)
    return len(q) >= MIN_QUOTE_CHARS and q in _normalize(page_text)


def keep_sourced(items: list[Fact] | list[Person], pages: dict[str, str]) -> tuple[list, list]:
    """Split facts (or people) into kept and dropped. Dropped get a reason for the log."""
    kept, dropped = [], []
    for item in items:
        page = pages.get(item.url)
        if page is None:
            dropped.append((item, "URL was not one of the pages we fetched."))
        elif not quote_on_page(item.quote, page):
            dropped.append((item, "Quote is not on the page."))
        else:
            kept.append(item)
    return kept, dropped


def keep_cited(reasons: list[Reason], allowed_evidence_ids: set[int]) -> list[Reason]:
    """Drop reasons that cite nothing, or cite evidence this company does not have."""
    return [
        r
        for r in reasons
        if r.evidence_ids and all(eid in allowed_evidence_ids for eid in r.evidence_ids)
    ]


def drop_repeats(reasons: list[Reason]) -> list[Reason]:
    """One fact counts once. A plus reason whose evidence was all used by a bigger plus
    reason is the same signal said twice (e.g. "wholesale" and "multi-channel via
    wholesale"), so it is dropped."""
    used: set[int] = set()
    kept = []
    for r in sorted(reasons, key=lambda x: -x.points):
        if set(r.evidence_ids) <= used:
            continue
        used |= set(r.evidence_ids)
        kept.append(r)
    return kept


SURE = ("high", "medium")


def size_rule(revenue: str, revenue_conf: str, staff: str, staff_conf: str) -> tuple[int, str]:
    """Hard size rules from the ICP, applied by code: (max score allowed, why). 100 = no cap."""
    if revenue == "over_10m" and revenue_conf in SURE:
        return 30, "Too big: over $10M revenue."
    if staff == "over_50" and staff_conf in SURE:
        return 30, "Too big: over 50 staff."
    if staff == "under_5" and staff_conf in SURE:
        return 40, "Too small: under 5 staff."
    if revenue == "under_1m" and revenue_conf in SURE:
        return 40, "Too small: under $1M revenue."
    return 100, ""


def score_and_verdict(
    reasons_for: list[Reason],
    reasons_against: list[Reason],
    confidence: float,
    min_conf: float,
    size_cap: int = 100,
    size_known: bool = True,
) -> tuple[int, str]:
    """Score = 50 + sum of reason points, kept in 0-100. Code decides the verdict, not the LLM.

    good >= 70, maybe 45-69, poor < 45. A clear size miss caps the score (size_rule).
    A "good" with low confidence, or with no proof of size at all, becomes "maybe", so a
    person looks at it (rule 5).
    """
    points = sum(r.points for r in reasons_for) + sum(r.points for r in reasons_against)
    score = max(0, min(100, size_cap, 50 + points))
    if score >= 70:
        verdict = "good"
    elif score >= 45:
        verdict = "maybe"
    else:
        verdict = "poor"
    if verdict == "good" and (confidence < min_conf or not size_known):
        verdict = "maybe"
    return score, verdict


def seen_in_results(name: str, domain: str, observations: str) -> bool:
    """A candidate must come from a real tool result: its domain (or name) is in the text."""
    text = observations.lower()
    d = domain.lower().removeprefix("www.")
    return (len(d) > 3 and d in text) or (len(name) > 3 and name.lower() in text)


def clean_domain(domain: str) -> str:
    d = domain.lower().strip()
    d = re.sub(r"^https?://", "", d).split("/")[0]
    return d.removeprefix("www.")


def align_quick_verdicts(domains: list[str], verdicts: list[QuickVerdict]) -> dict[str, tuple]:
    """Map each domain to (keep, reason). A domain the LLM skipped is kept: unsure = keep."""
    by_domain = {v.domain.lower().strip(): v for v in verdicts}
    result = {}
    for d in domains:
        v = by_domain.get(d.lower())
        result[d] = (v.keep, v.reason) if v else (True, "Filter gave no answer; kept to be safe.")
    return result


class BudgetExceeded(Exception):
    pass


@dataclass
class ToolBudget:
    """Hard cap on the search agent's tool calls and paid search credits per campaign."""

    max_calls: int = 25
    max_credits: int = 300
    calls: int = 0
    credits: int = 0
    log: list[str] = field(default_factory=list)

    def spend(self, tool: str, credits: int = 0) -> None:
        if self.calls + 1 > self.max_calls:
            raise BudgetExceeded(f"Tool call limit reached ({self.max_calls}).")
        if self.credits + credits > self.max_credits:
            raise BudgetExceeded(f"Search credit limit reached ({self.max_credits}).")
        self.calls += 1
        self.credits += credits
        self.log.append(tool)
