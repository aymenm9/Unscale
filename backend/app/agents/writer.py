"""Email writer: strategy + first email, follow-ups on their due day, and the fact checker.

Flow for every email: LLM writes -> code checks -> (one retry with the errors) ->
LLM fact checker -> (one retry with the problems). Anything still failing is kept as a
draft with the failed checks shown, and a person decides.
"""

import difflib
import json

from app.agents import llm
from app.agents.prompts import COMPOSE_REWRITE, FACT_CHECK, FOLLOW_UP, STRATEGY_FIRST_EMAIL
from app.agents.schemas import FactCheckResult, FirstEmail, FollowUp, Rewrite
from app.config import settings
from app.guards.email import check_email, failed, renumber_markers


def _evidence_text(evidence: list[dict]) -> str:
    return "\n".join(f'id {e["id"]}: {e["claim"]} (quote: "{e["quote"]}")' for e in evidence)


def fact_check(body: str, citations: list[int], evidence: list[dict]) -> list[str]:
    """Return problems (empty = every sentence is supported). LLM errors count as a problem."""
    by_id = {e["id"]: e for e in evidence}
    cited = "\n".join(
        f"[{n}] {by_id[eid]['quote']}" for n, eid in enumerate(citations, 1) if eid in by_id
    )
    user = f"<email>\n{body}\n</email>\n\nCITED EVIDENCE:\n<page>\n{cited or 'none'}\n</page>"
    try:
        result = llm.structured(FACT_CHECK, user, FactCheckResult, chain_names=settings.llm_check)
    except Exception as e:
        return [f"Fact checker failed: {llm.user_message(e) if llm.is_down(e) else e}"]
    return [
        f"{s.sentence} -> {s.problem or 'unsupported'}" for s in result.sentences if not s.supported
    ]


def _fact_check_item(problems: list[str]) -> dict:
    return {
        "name": "fact_check",
        "passed": not problems,
        "detail": "Every sentence is backed by its source."
        if not problems
        else "Unsupported: " + "; ".join(problems),
    }


def write_first(
    company: str,
    contact: dict,
    evidence: list[dict],
    campaign: dict,
    suppressed: set[str],
) -> dict:
    """Returns {subject, body, citations, strategy, checks, handoff_reason}."""
    allowed = {e["id"] for e in evidence}
    user = (
        f"Company: {company}\nContact: {contact.get('name') or 'unknown name (write Hi there,)'}, "
        f"{contact.get('title', '')}\nCampaign voice preference: {campaign.get('voice', 'auto')}\n\n"
        f"EVIDENCE:\n<page>\n{_evidence_text(evidence)}\n</page>"
    )
    feedback = ""
    email = None
    checks: list[dict] = []
    for _attempt in range(3):
        email = llm.structured(
            STRATEGY_FIRST_EMAIL, user + feedback, FirstEmail, chain_names=settings.llm_write
        )
        body, cits = renumber_markers(email.body, email.citations, allowed)
        email = email.model_copy(update={"body": body, "citations": cits})
        checks = check_email(
            "first",
            email.subject,
            email.body,
            email.citations,
            allowed,
            contact.get("email", "").lower(),
            suppressed,
        )
        if email.strategy.trigger_evidence_id not in allowed:
            checks.append(
                {
                    "name": "strategy_trigger",
                    "passed": False,
                    "detail": "The strategy's trigger is not one of this company's facts.",
                }
            )
        problems = failed(checks)
        if not problems:
            fc = fact_check(email.body, email.citations, evidence)
            checks.append(_fact_check_item(fc))
            problems = fc
        if not problems:
            break
        feedback = (
            f"\n\nYOUR LAST DRAFT:\nSubject: {email.subject}\n{email.body}\n\n"
            "IT FAILED THESE CHECKS. Edit that draft to fix them, keep what was fine:\n"
            + "\n".join(problems)
        )

    assert email is not None
    # The agent fixes check failures itself (3 tries). Only what it could not fix reaches a
    # person, as a plain note on the draft.
    still_failing = [c["detail"] for c in checks if not c["passed"]]
    handoff = email.handoff_reason or ""
    if still_failing:
        handoff = (
            "I tried 3 times and this rule is still broken: "
            + " ".join(still_failing)
            + " Please edit the email, or ask me to redo it."
        )
    strategy = email.strategy.model_dump()
    for a in strategy["follow_up_angles"]:
        if a.get("evidence_id") not in allowed:
            a["evidence_id"] = None
    return {
        "subject": email.subject,
        "body": email.body,
        "citations": email.citations,
        "strategy": strategy,
        "checks": checks,
        "handoff_reason": handoff,
    }


def write_follow_up(
    step: int,
    strategy: dict,
    thread_text: str,
    evidence: list[dict],
    recipient: str,
    suppressed: set[str],
) -> dict:
    """Returns {body, citations, checks, ok, handoff_reason}."""
    allowed = {e["id"] for e in evidence}
    user = (
        f"STEP: {step}\nAPPROVED STRATEGY: {json.dumps(strategy)}\n\n"
        f"EVIDENCE:\n<page>\n{_evidence_text(evidence)}\n</page>\n\n<thread>\n{thread_text}\n</thread>"
    )
    feedback = ""
    fu = None
    checks: list[dict] = []
    for _attempt in range(2):
        fu = llm.structured(FOLLOW_UP, user + feedback, FollowUp, chain_names=settings.llm_write)
        body, cits = renumber_markers(fu.body, fu.citations, allowed)
        fu = fu.model_copy(update={"body": body, "citations": cits})
        checks = check_email(
            "follow_up", None, fu.body, fu.citations, allowed, recipient, suppressed
        )
        problems = failed(checks)
        if not problems and fu.citations:
            fc = fact_check(fu.body, fu.citations, evidence)
            checks.append(_fact_check_item(fc))
            problems = fc
        if not problems:
            break
        feedback = "\n\nYOUR LAST DRAFT FAILED THESE CHECKS. Fix them:\n" + "\n".join(problems)
    assert fu is not None
    ok = not failed(checks) and fu.confidence != "low" and not fu.handoff_reason
    return {
        "body": fu.body,
        "citations": fu.citations,
        "checks": checks,
        "ok": ok,
        "handoff_reason": fu.handoff_reason or ("" if ok else "Follow-up did not pass checks."),
    }


FULL_REWRITE_WORDS = ("rewrite", "from scratch", "start over", "new version", "completely")
MIN_KEPT = 0.45  # share of the original wording a normal edit should keep


def kept_share(before: str, after: str) -> float:
    """How much of the original wording survived (0..1), word by word."""
    return difflib.SequenceMatcher(None, before.lower().split(), after.lower().split()).ratio()


def rewrite(context: str, body: str, comment: str) -> Rewrite:
    """Edit the person's email as their comment asks. Code checks the AI kept their email:
    if it replaced too much (and they did not ask for a full rewrite), it gets one retry."""
    user = (
        f"COMMENT: {comment}\n\nCURRENT EMAIL:\n<email>\n{body}\n</email>\n\n"
        f"BACKGROUND (do not add from it unless the comment asks):\n{context}"
    )
    result = llm.structured(COMPOSE_REWRITE, user, Rewrite, chain_names=settings.llm_write)
    wants_full = any(w in comment.lower() for w in FULL_REWRITE_WORDS)
    if not wants_full and len(body.split()) >= 5 and kept_share(body, result.body) < MIN_KEPT:
        retry = (
            f"{user}\n\nYOUR LAST VERSION CHANGED TOO MUCH:\n{result.body}\n\n"
            "Start again from CURRENT EMAIL. Keep their sentences; change only what the "
            "COMMENT asks."
        )
        result = llm.structured(COMPOSE_REWRITE, retry, Rewrite, chain_names=settings.llm_write)
    return result
