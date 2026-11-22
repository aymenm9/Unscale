"""Quick filter with decision models: code turns the probabilities into keep/drop."""

import pytest

from app.agents import quick_filter
from app.agents.quick_filter import DecisionFailed, decide
from app.config import settings


def answer(**probs):
    return {"type": "choice", "choice": max(probs, key=probs.get), "probabilities": probs}


def test_clear_fit_is_kept():
    keep, reason = decide(answer(keep=0.9, not_a_store=0.05, too_big=0.05), "Gemini Decision")
    assert keep is True
    assert reason == "Gemini Decision: worth researching (90% keep)."


def test_clear_miss_is_dropped_with_the_main_reason():
    keep, reason = decide(answer(keep=0.05, not_a_store=0.85, too_big=0.1), "Gemini Decision")
    assert keep is False
    assert reason == "Not a brand selling its own products (Gemini Decision, 85% sure)."


def test_unsure_is_kept_even_when_keep_is_not_the_top_choice():
    # The model leans "too big" but keep is still 30%: a wrong "no" costs more than a wrong "yes".
    keep, _ = decide(answer(keep=0.30, too_big=0.70))
    assert keep is True


def test_missing_keep_probability_counts_as_keep():
    keep, _ = decide({"probabilities": {"too_big": 0.6}})
    assert keep is True


def fail(campaign, company):
    raise DecisionFailed("daily limit")


def test_gemini_decision_is_tried_first(monkeypatch):
    monkeypatch.setattr(quick_filter, "ask_gemini_decision", lambda c, x: answer(keep=0.95))
    monkeypatch.setattr(quick_filter, "ask_clef", lambda c, x: pytest.fail("Clef not needed"))
    out = quick_filter.run({}, [{"domain": "a.com"}])
    assert out["a.com"] == (True, "Gemini Decision: worth researching (95% keep).")


def test_clef_answers_when_gemini_decision_fails(monkeypatch):
    monkeypatch.setattr(quick_filter, "ask_gemini_decision", fail)
    monkeypatch.setattr(quick_filter, "ask_clef", lambda c, x: answer(keep=0.02, outside_us=0.98))
    out = quick_filter.run({}, [{"domain": "a.ca"}])
    assert out["a.ca"] == (False, "Based outside the US (Clef, 98% sure).")


def test_chat_model_answers_when_both_decision_models_fail(monkeypatch):
    used = []

    def fallback(campaign, companies):
        used.append(len(companies))
        return {c["domain"]: (True, "chat model") for c in companies}

    monkeypatch.setattr(quick_filter, "ask_gemini_decision", fail)
    monkeypatch.setattr(quick_filter, "ask_clef", fail)
    monkeypatch.setattr(quick_filter, "llm_batch", fallback)
    out = quick_filter.run({}, [{"domain": "a.com"}, {"domain": "b.com"}])
    assert used == [2]
    assert out["a.com"] == (True, "chat model")


def test_not_configured_raises(monkeypatch):
    monkeypatch.setattr(settings, "gemini_decision_model", "")
    monkeypatch.setattr(settings, "clef_model", "")
    with pytest.raises(DecisionFailed):
        quick_filter.ask_gemini_decision({}, {"domain": "a.com"})
    with pytest.raises(DecisionFailed):
        quick_filter.ask_clef({}, {"domain": "a.com"})


def test_both_apis_answer_in_the_same_shape():
    a = {"fit": {"type": "choice", "choice": "keep", "probabilities": {"keep": 0.97}}}
    assert quick_filter.read_fit_answer(a)["choice"] == "keep"
    with pytest.raises(DecisionFailed):
        quick_filter.read_fit_answer({})


def test_everyone_kept_when_every_filter_fails():
    # Both decision models are switched off in tests and no chat provider is set.
    out = quick_filter.run({}, [{"domain": "a.com", "name": "A"}])
    assert out["a.com"][0] is True
