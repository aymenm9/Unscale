"""When no AI can answer, the sales team is told why in plain words, not a bare error code."""

from app.agents import llm
from app.api import routes
from tests.test_llm_chain import GOOD, Out, configure, fake_openai


def limit_hit(minutes):
    return RuntimeError(f"Error code: 429 rate limit reached, try again in {minutes}m")


def test_all_providers_at_their_limit_says_when_to_come_back(monkeypatch):
    configure(monkeypatch, ["groq", "opencode"])
    fake_openai(monkeypatch, {"groq": [limit_hit(14)], "opencode": [limit_hit(30)]})
    try:
        llm.structured("s", "u", Out)
    except llm.LLMFailed as e:
        assert e.rate_limited is True
        assert e.retry_in == 14 * 60 + 1  # the soonest provider
        text = llm.user_message(e)
        assert "used up their limits" in text and "about 14 minutes" in text
    else:
        raise AssertionError("expected LLMFailed")


def test_providers_down_is_not_called_a_limit(monkeypatch):
    configure(monkeypatch, ["groq", "opencode"])
    fake_openai(monkeypatch, {"groq": [limit_hit(5)], "opencode": [RuntimeError("502")]})
    try:
        llm.structured("s", "u", Out)
    except llm.LLMFailed as e:
        assert e.rate_limited is False
        assert "failed just now" in llm.user_message(e)
    else:
        raise AssertionError("expected LLMFailed")


def test_status_turns_red_only_when_every_provider_rests(monkeypatch):
    configure(monkeypatch, ["groq", "opencode"])
    assert llm.status()["ok"] is True
    fake_openai(monkeypatch, {"groq": [limit_hit(10)], "opencode": [limit_hit(20), GOOD]})
    try:
        llm.structured("s", "u", Out)
    except llm.LLMFailed:
        pass
    s = llm.status()
    assert s["ok"] is False and s["resting"] == 2
    assert "about 10 minutes" in s["message"]


def test_api_answers_503_with_a_plain_message(client, monkeypatch):
    def used_up(*_a, **_k):
        raise llm.LLMFailed("groq: 429", rate_limited=True, retry_in=840)

    monkeypatch.setattr(routes, "write_draft", used_up)
    draft = client.get("/api/review").json()[0]
    res = client.post(f"/api/review/{draft['id']}/redo")
    assert res.status_code == 503
    assert res.headers["Retry-After"] == "840"
    body = res.json()
    assert body["code"] == "ai_limits_used_up"
    assert "about 14 minutes" in body["detail"]


def test_ai_status_endpoint_reports_missing_setup(client):
    s = client.get("/api/ai-status").json()  # the test client has no provider configured
    assert s["ok"] is False
    assert "not set up" in s["message"]
