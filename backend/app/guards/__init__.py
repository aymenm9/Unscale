"""Deterministic guardrails (rules 1-3 of the brief). Plain regex, no LLM.

They are biased to be safe: a false "opt-out" only loses a lead, a missed one breaks a rule.
"""

import re

from app.config import settings

# ---------- Rule 3: stop / unsubscribe / not interested ----------

OPT_OUT_PATTERNS = [
    r"\bunsubscribe\b",
    r"\bnot interested\b",
    r"\bopt[\s-]?out\b",
    r"\bremove me\b",
    r"\btake me off\b",
    r"\bstop (emailing|contacting|messaging|sending|writing)\b",
    r"\b(don'?t|do not) (contact|email|message|write to) me\b",
    r"^\W*stop\W*$",  # the message is just "stop"
]


def is_opt_out(text: str) -> bool:
    t = text.lower().strip()
    # "interested but not right now" is a timing objection, not an opt-out.
    return any(re.search(p, t) for p in OPT_OUT_PATTERNS)


# ---------- Rule 4: "are you a bot?" ----------

BOT_PATTERNS = [
    r"\bare you (a |an )?(bot|robot|ai|human|real|person|machine)\b",
    r"\bis this (a |an )?(bot|ai|automated|real person|human)\b",
    r"\bis this (email|message) automated\b",
    r"\b(real|actual) (person|human)\b",
    r"\b(written|sent|generated) by (a |an )?(bot|ai|chatgpt|gpt|machine)\b",
    r"\bchatgpt\b",
]


def asks_if_bot(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in BOT_PATTERNS)


# ---------- Rule 1: never quote a price ----------

MONEY = r"(\$\s?\d[\d,.]*\s?k?|\d[\d,.]*\s?k?\s?(usd|dollars)|usd\s?\d[\d,.]*)"
PERIOD = r"(/\s?(mo|month|yr|year|hr|hour)|per (month|year|hour)|a (month|year)|monthly|annually)"
PRICE_PATTERNS = [
    MONEY + r"\s*" + PERIOD,  # "$500/month", "400 dollars a month"
    r"\d[\d,.]*\s?k\s?" + PERIOD,  # "2k/month"
    r"\b(price|pricing|cost|costs|fee|fees|plans?|rate)\b[^.?!]{0,40}"
    + MONEY,  # "plans start at $500"
    r"\bbetween\s+" + MONEY + r"\s+and\s+" + MONEY,
    r"\busd\s?\d",
    r"\b(affordable|cheap|cheaper|discount|discounted|fraction of the cost)\b",
]


def contains_price(text: str) -> bool:
    t = text.lower()
    # Revenue bands like "$1-10M" or "$5M in revenue" are about the prospect, not a price.
    return any(re.search(p, t) for p in PRICE_PATTERNS)


# ---------- Demo safety: never email a real prospect ----------


def outbound_recipient(real_email: str, test_email: str = "") -> str:
    """Every outbound email is redirected: to the tester's own inbox when test mode is on,
    else to the demo inbox. The real company address is never used, only logged."""
    return test_email or settings.demo_inbox


# ---------- Pre-send checks for a first email ----------


def check_draft(
    body: str,
    citations: list[int],
    allowed_evidence_ids: set[int],
    recipient: str,
    suppressed_emails: set[str],
) -> list[dict]:
    """Return the checks the reviewer sees next to the draft. Sending needs all to pass."""
    markers = {int(m) for m in re.findall(r"\[(\d+)\]", body)}
    citations_ok = all(cid in allowed_evidence_ids for cid in citations) and markers == set(
        range(1, len(citations) + 1)
    )
    return [
        {
            "name": "no_price",
            "passed": not contains_price(body),
            "detail": "No price or price range in the email.",
        },
        {
            "name": "has_personal_fact",
            "passed": len(citations) > 0,
            "detail": "At least one sourced fact about the company.",
        },
        {
            "name": "citations_valid",
            "passed": citations_ok,
            "detail": "Every [n] marker points to stored evidence for this company.",
        },
        {
            "name": "not_suppressed",
            "passed": recipient.lower() not in suppressed_emails,
            "detail": "Recipient is not on the do-not-contact list.",
        },
    ]
