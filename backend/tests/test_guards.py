"""Deterministic guardrails. These run before and after every LLM call."""

import pytest

from app.guards import (
    asks_if_bot,
    check_draft,
    contains_price,
    is_opt_out,
    outbound_recipient,
)


@pytest.mark.parametrize(
    "text",
    [
        "STOP",
        "stop",
        "Unsubscribe",
        "please unsubscribe me",
        "Not interested, thanks.",
        "not interested",
        "Remove me from your list",
        "take me off this list please",
        "Please stop emailing me.",
        "Don't contact me again",
        "do not email me",
        "opt out",
        "We're not interested at this time.",
    ],
)
def test_opt_out_detected(text):
    assert is_opt_out(text)


@pytest.mark.parametrize(
    "text",
    [
        "Sounds interesting, what does onboarding look like?",
        "Can we talk Tuesday at 2pm?",
        "We can't stop growing, that's the problem with our books!",
        "I'm interested but not right now, maybe next quarter",
        "How much does it cost?",
    ],
)
def test_opt_out_not_triggered(text):
    assert not is_opt_out(text)


@pytest.mark.parametrize(
    "text",
    [
        "Are you a bot?",
        "is this an AI?",
        "Am I talking to a real person?",
        "Is this email automated?",
        "are you human",
        "Was this written by ChatGPT?",
    ],
)
def test_bot_question_detected(text):
    assert asks_if_bot(text)


def test_bot_question_not_triggered():
    assert not asks_if_bot("Can your team handle Shopify payouts?")


@pytest.mark.parametrize(
    "text",
    [
        "Our plans start at $500/month.",
        "It's usually around 400 dollars a month",
        "Pricing is $1,200 per month for your size",
        "between $300 and $900",
        "about 2k/month",
        "USD 450",
    ],
)
def test_price_detected(text):
    assert contains_price(text)


@pytest.mark.parametrize(
    "text",
    [
        "Pricing depends on your setup, happy to walk through it on a call.",
        "You crossed $5M in revenue last year [1].",
        "We work with brands doing $1-10M in revenue.",
    ],
)
def test_price_not_triggered(text):
    # Company revenue figures are not prices. Only money-per-period or "pricing is $X" counts.
    assert not contains_price(text)


def test_outbound_always_goes_to_demo_inbox():
    assert outbound_recipient("ceo@realcompany.com") == "delivered@resend.dev"


def test_check_draft_passes_clean_email():
    checks = check_draft(
        body="Hi Ana, saw you're hiring an ops lead [1]. Worth a call?",
        citations=[11],
        allowed_evidence_ids={11, 12},
        recipient="ana@brand.com",
        suppressed_emails=set(),
    )
    assert all(c["passed"] for c in checks), checks


def test_check_draft_catches_problems():
    checks = check_draft(
        body="Hi Ana, plans start at $500/month [1] and you raised money [2].",
        citations=[11, 99],
        allowed_evidence_ids={11},
        recipient="ana@brand.com",
        suppressed_emails={"ana@brand.com"},
    )
    failed = {c["name"] for c in checks if not c["passed"]}
    assert failed == {"no_price", "citations_valid", "not_suppressed"}


def test_check_draft_requires_citation_markers_to_match():
    checks = check_draft(
        body="Hi Ana, you launched wholesale [1] and moved to Shopify [2].",
        citations=[11],
        allowed_evidence_ids={11},
        recipient="ana@brand.com",
        suppressed_emails=set(),
    )
    assert {c["name"] for c in checks if not c["passed"]} == {"citations_valid"}


def test_check_draft_requires_at_least_one_fact():
    checks = check_draft(
        body="Hi Ana, want to chat about bookkeeping?",
        citations=[],
        allowed_evidence_ids={11},
        recipient="ana@brand.com",
        suppressed_emails=set(),
    )
    assert {c["name"] for c in checks if not c["passed"]} == {"has_personal_fact"}


def test_markers_written_as_evidence_ids_are_renumbered():
    from app.guards.email import renumber_markers

    body, cits = renumber_markers(
        "Saw the round [42]. And wholesale [17], again [42].", [], {17, 42}
    )
    assert body == "Saw the round [1]. And wholesale [2], again [1]."
    assert cits == [42, 17]
    # already positions: unchanged
    assert renumber_markers("A [1] b [2]", [5, 6], {5, 6}) == ("A [1] b [2]", [5, 6])
    # unknown id: left alone so the checks catch it
    assert renumber_markers("A [99]", [], {5}) == ("A [99]", [])
