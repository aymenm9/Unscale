"""Reply agent tests with a fake LLM, so they are free and deterministic."""

import pytest

from app.agents import llm, reply
from app.agents.reply import Analysis, Reply


def fake_llm(monkeypatch, analysis: Analysis | Exception, reply_body: str = "Happy to help."):
    calls = []

    def structured(system, user, schema, chain_names=None):
        calls.append(schema)
        if schema is Analysis:
            if isinstance(analysis, Exception):
                raise analysis
            return analysis
        return Reply(body=reply_body, offer_slots=False)

    monkeypatch.setattr(llm, "structured", structured)
    return calls


def run(text, **extra):
    state = {"inbound": text, "history": "", "company_name": "Fernhill", "contact_name": "Ana"}
    state.update(extra)
    return reply.decide(state)


def a(intent, confidence=0.95, bot=False, slot=None):
    return Analysis(
        intent=intent,
        also_asks_if_bot=bot,
        confidence=confidence,
        picked_slot_index=slot,
        summary="test",
    )


def test_opt_out_never_reaches_llm(monkeypatch):
    calls = fake_llm(monkeypatch, a("question"))
    out = run("Please unsubscribe me")
    assert out["action"] == "suppress"
    assert calls == []  # deterministic guard fired first


def test_llm_opt_out_also_suppresses(monkeypatch):
    fake_llm(monkeypatch, a("opt_out"))
    assert run("We'll pass, all good.")["action"] == "suppress"


def test_low_confidence_hands_off(monkeypatch):
    fake_llm(monkeypatch, a("question", confidence=0.4))
    out = run("hmm what")
    assert out["action"] == "handoff"
    assert "Low confidence" in out["reason"]


def test_other_intent_hands_off(monkeypatch):
    fake_llm(monkeypatch, a("other"))
    assert run("Who gave you my email? I'm calling my lawyer.")["action"] == "handoff"


def test_classifier_error_hands_off(monkeypatch):
    fake_llm(monkeypatch, RuntimeError("boom"))
    assert run("Tell me more")["action"] == "handoff"


def test_no_api_key_hands_off(monkeypatch):
    fake_llm(monkeypatch, llm.LLMNotConfigured("no key"))
    assert run("Tell me more")["action"] == "handoff"


def test_price_in_llm_reply_is_blocked(monkeypatch):
    fake_llm(monkeypatch, a("pricing"), reply_body="Most clients pay about $600/month.")
    out = run("How much is it?")
    assert out["action"] == "handoff"
    assert "price" in out["reason"]


def test_question_gets_reply(monkeypatch):
    fake_llm(monkeypatch, a("question"), reply_body="Yes, we reconcile Shopify payouts monthly.")
    out = run("Do you handle Shopify payouts?")
    assert out["action"] == "send"
    assert "Shopify" in out["reply"]


def test_bot_question_disclosure_added_when_llm_forgets(monkeypatch):
    fake_llm(monkeypatch, a("bot_question"), reply_body="Great question! Happy to set up a call.")
    out = run("Are you a bot?")
    assert out["action"] == "send"
    assert out["reply"].startswith(reply.AI_DISCLOSURE)


def test_bot_disclosure_not_duplicated(monkeypatch):
    body = "Yes, I'm an AI assistant for the Ledgerwise team. A person reads every thread."
    fake_llm(monkeypatch, a("bot_question"), reply_body=body)
    assert run("is this an AI?")["reply"] == body


def test_picked_valid_slot_books(monkeypatch):
    fake_llm(monkeypatch, a("picked_time", slot=1))
    out = run("Thursday works", offered_slots=["Tue 10:00", "Thu 14:00"])
    assert out["action"] == "book"
    assert out["slot_index"] == 1


@pytest.mark.parametrize("slot", [None, 5])
def test_picked_unknown_slot_hands_off(monkeypatch, slot):
    fake_llm(monkeypatch, a("picked_time", slot=slot))
    out = run("How about Saturday?", offered_slots=["Tue 10:00"])
    assert out["action"] == "handoff"
