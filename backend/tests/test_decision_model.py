"""Quick filter with Cloudflare Clef: code turns Clef's probabilities into keep/drop."""

from app.agents import quick_filter
from app.agents.quick_filter import ClefFailed, decide
from app.config import settings


def answer(**probs):
    return {"type": "choice", "choice": max(probs, key=probs.get), "probabilities": probs}


def test_clear_fit_is_kept():
    keep, reason = decide(answer(keep=0.9, not_a_store=0.05, too_big=0.05))
    assert keep is True
    assert "90% keep" in reason


def test_clear_miss_is_dropped_with_the_main_reason():
    keep, reason = decide(answer(keep=0.05, not_a_store=0.85, too_big=0.1))
    assert keep is False
    assert reason == "Not a brand selling its own products (decision model, 85% sure)."


def test_unsure_is_kept_even_when_keep_is_not_the_top_choice():
    # Clef leans "too big" but keep is still 30%: a wrong "no" costs more than a wrong "yes".
    keep, _ = decide(answer(keep=0.30, too_big=0.70))
    assert keep is True


def test_missing_keep_probability_counts_as_keep():
    keep, _ = decide({"probabilities": {"too_big": 0.6}})
    assert keep is True


def test_clef_failure_falls_back_to_the_chat_model(monkeypatch):
    def broken(campaign, company):
        raise ClefFailed("daily limit")

    used = []

    def fallback(campaign, companies):
        used.append(len(companies))
        return {c["domain"]: (True, "chat model") for c in companies}

    monkeypatch.setattr(quick_filter, "ask_clef", broken)
    monkeypatch.setattr(quick_filter, "llm_batch", fallback)
    out = quick_filter.run({}, [{"domain": "a.com"}, {"domain": "b.com"}])
    assert used == [2]
    assert out["a.com"] == (True, "chat model")


def test_clef_not_configured_raises(monkeypatch):
    monkeypatch.setattr(settings, "decision_model", "")
    try:
        quick_filter.ask_clef({}, {"domain": "a.com"})
    except ClefFailed:
        return
    raise AssertionError("expected ClefFailed")


def test_everyone_kept_when_both_filters_fail(monkeypatch):
    # decision_model is empty in tests and no chat provider is set: nobody gets dropped.
    out = quick_filter.run({}, [{"domain": "a.com", "name": "A"}])
    assert out["a.com"][0] is True
