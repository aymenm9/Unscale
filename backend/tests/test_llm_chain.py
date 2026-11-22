"""Provider pool: skip unconfigured, fall through on errors and bad JSON, rotate, rest on 429."""

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.agents import llm
from app.config import settings


class Out(BaseModel):
    intent: str
    confidence: float


def configure(monkeypatch, names):
    monkeypatch.setattr(settings, "llm_providers", ",".join(names))
    for n in names:
        monkeypatch.setattr(settings, f"{n}_api_key", "k", raising=False)
        monkeypatch.setattr(settings, f"{n}_base_url", f"https://{n}.test/v1", raising=False)
        monkeypatch.setattr(settings, f"{n}_model", "m", raising=False)


def fake_openai(monkeypatch, replies_by_host):
    """replies_by_host: {"groq": [Exception | str, ...]} consumed in order."""
    used = []

    class FakeClient:
        def __init__(self, base_url, **_):
            self.host = base_url.split("//")[1].split(".")[0]
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **_):
            used.append(self.host)
            nxt = replies_by_host[self.host].pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            msg = SimpleNamespace(content=nxt)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    monkeypatch.setattr(llm, "OpenAI", FakeClient)
    return used


GOOD = '{"intent": "question", "confidence": 0.9}'


def test_no_provider_configured(monkeypatch):
    monkeypatch.setattr(settings, "llm_providers", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "")
    with pytest.raises(llm.LLMNotConfigured):
        llm.structured("s", "u", Out)


def test_first_provider_answers(monkeypatch):
    configure(monkeypatch, ["groq", "opencode"])
    used = fake_openai(monkeypatch, {"groq": [GOOD], "opencode": []})
    assert llm.structured("s", "u", Out).intent == "question"
    assert used == ["groq"]


def test_falls_through_on_error(monkeypatch):
    configure(monkeypatch, ["groq", "opencode"])
    used = fake_openai(monkeypatch, {"groq": [RuntimeError("429")], "opencode": [GOOD]})
    assert llm.structured("s", "u", Out).confidence == 0.9
    assert used == ["groq", "opencode"]


def test_retries_once_on_bad_json_then_succeeds(monkeypatch):
    configure(monkeypatch, ["groq"])
    used = fake_openai(monkeypatch, {"groq": ['{"intent": "question"}', GOOD]})
    assert llm.structured("s", "u", Out).intent == "question"
    assert used == ["groq", "groq"]


def test_accepts_fenced_json(monkeypatch):
    configure(monkeypatch, ["groq"])
    fake_openai(monkeypatch, {"groq": [f"```json\n{GOOD}\n```"]})
    assert llm.structured("s", "u", Out).intent == "question"


def test_all_fail_raises(monkeypatch):
    configure(monkeypatch, ["groq", "opencode"])
    fake_openai(monkeypatch, {"groq": ["nope", "nope"], "opencode": [RuntimeError("down")]})
    with pytest.raises(llm.LLMFailed):
        llm.structured("s", "u", Out)


def test_calls_rotate_across_the_pool(monkeypatch):
    configure(monkeypatch, ["groq", "gonka", "opencode"])
    used = fake_openai(monkeypatch, {"groq": [GOOD], "gonka": [GOOD], "opencode": [GOOD]})
    for _ in range(3):
        llm.structured("s", "u", Out)
    assert used == ["groq", "gonka", "opencode"]  # each call starts at the next one


def test_several_keys_become_separate_entries(monkeypatch):
    configure(monkeypatch, ["groq"])
    monkeypatch.setattr(settings, "groq_api_key", "k1, k2")
    names = [p.name for p in llm.providers()]
    assert names == ["groq#1", "groq#2"]
    assert [p.api_key for p in llm.providers()] == ["k1", "k2"]


def test_rate_limited_provider_rests(monkeypatch):
    configure(monkeypatch, ["groq", "gonka"])
    limit = RuntimeError("Error code: 429 - Rate limit reached. Please try again in 14m26.1s.")
    used = fake_openai(monkeypatch, {"groq": [limit], "gonka": [GOOD, GOOD, GOOD]})
    llm.structured("s", "u", Out)  # groq hits the limit, gonka answers
    llm.structured("s", "u", Out)  # rotation would start at gonka anyway
    llm.structured("s", "u", Out)  # rotation says groq, but groq is resting
    assert used == ["groq", "gonka", "gonka", "gonka"]


def test_cooldown_reads_the_wait_time():
    assert llm.cooldown_seconds(RuntimeError("429 ... try again in 14m26.1s")) == 867
    assert llm.cooldown_seconds(RuntimeError("429 Too Many Requests")) == llm.DEFAULT_COOLDOWN
    assert llm.cooldown_seconds(RuntimeError("500 server error")) is None


def test_entry_can_pick_a_model_for_a_job(monkeypatch):
    configure(monkeypatch, ["groq"])
    pool = llm.providers("groq:openai/gpt-oss-20b,groq")
    assert [(p.name, p.model) for p in pool] == [
        ("groq:openai/gpt-oss-20b", "openai/gpt-oss-20b"),
        ("groq", "m"),
    ]
