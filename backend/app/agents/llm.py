"""The only place that calls an LLM. Every call returns a validated Pydantic object.

Providers are free OpenAI-compatible APIs (Groq, Cloudflare, OpenCode Zen, AxForge, Gonka).
They form a pool that rotates:
- Each provider may have several keys (GROQ_API_KEY=key1,key2). Each key is one pool entry.
- Each call starts at the next entry (round-robin), so free daily limits are shared out.
- If an entry errors or returns bad JSON, the next one is tried.
- If an entry hits a rate limit (429), it rests until its cooldown ends ("try again in 14m").
A provider is left out when its key, model or base URL is empty.
"""

import json
import logging
import re
import threading
import time
from dataclasses import dataclass

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from app.config import settings

log = logging.getLogger(__name__)


class LLMNotConfigured(Exception):
    """No provider has a key + model set."""


class LLMFailed(Exception):
    """Every configured provider failed."""


@dataclass
class Provider:
    name: str
    base_url: str
    api_key: str
    model: str
    json_mode: bool = True  # sends response_format=json_object
    system_role: bool = True  # some models (older Gemma models) reject a system message


def providers(names: str | None = None) -> list[Provider]:
    """Configured pool entries from a comma list (default: LLM_PROVIDERS).
    A provider with 2 keys gives 2 entries: groq#1, groq#2."""
    found = []
    for entry in [p.strip() for p in (names or settings.llm_providers).split(",") if p.strip()]:
        # "groq" uses GROQ_MODEL; "groq:openai/gpt-oss-20b" picks a model for this job.
        name, _, model_override = entry.partition(":")
        base_url = getattr(settings, f"{name}_base_url", "")
        model = model_override or getattr(settings, f"{name}_model", "")
        keys = [k.strip() for k in getattr(settings, f"{name}_api_key", "").split(",") if k.strip()]
        if not (base_url and model):
            continue
        for i, key in enumerate(keys, start=1):
            label = entry if len(keys) == 1 else f"{entry}#{i}"
            found.append(
                Provider(
                    name=label,
                    base_url=base_url,
                    api_key=key,
                    model=model,
                    json_mode=getattr(settings, f"{name}_json_mode", True),
                    system_role=getattr(settings, f"{name}_system_role", True),
                )
            )
    return found


# ---------- rotation state (shared by all threads in this process) ----------

_lock = threading.Lock()
_next_start: dict[str, int] = {}  # pool -> index of the entry that goes first next time
_resting_until: dict[str, float] = {}  # entry name -> unix time when it may be used again
DEFAULT_COOLDOWN = 60  # seconds, when a 429 does not say how long to wait
MAX_COOLDOWN = 3600


def reset_rotation() -> None:
    """Forget rotation and cooldowns (used by tests)."""
    with _lock:
        _next_start.clear()
        _resting_until.clear()


def cooldown_seconds(error: Exception) -> int | None:
    """Seconds to rest after a rate limit, or None if this was not a rate limit."""
    text = str(error)
    if "429" not in text and "rate limit" not in text.lower():
        return None
    m = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", text)
    if m and any(m.groups()):
        h, mins, secs = (float(x) if x else 0 for x in m.groups())
        return min(MAX_COOLDOWN, int(h * 3600 + mins * 60 + secs) + 1)
    return DEFAULT_COOLDOWN


def rotation_order(pool_key: str, chain: list[Provider]) -> list[Provider]:
    """The chain starting at this pool's next entry, resting entries moved to the end."""
    with _lock:
        start = _next_start.get(pool_key, 0) % len(chain)
        _next_start[pool_key] = start + 1
        now = time.time()
        rotated = chain[start:] + chain[:start]
        ready = [p for p in rotated if _resting_until.get(p.name, 0) <= now]
        resting = [p for p in rotated if _resting_until.get(p.name, 0) > now]
        # Resting entries are still tried last, soonest-free first: better than failing.
        resting.sort(key=lambda p: _resting_until[p.name])
        return ready + resting


def _rest(p: Provider, seconds: int) -> None:
    with _lock:
        _resting_until[p.name] = time.time() + seconds


def _ask[T: BaseModel](p: Provider, system: str, user: str, schema: type[T]) -> T:
    """One provider, up to two tries (second try shows the model its validation error)."""
    client = OpenAI(base_url=p.base_url, api_key=p.api_key, timeout=60, max_retries=1)
    json_schema = schema.model_json_schema()
    instructions = (
        f"{system}\n\nReply with ONE JSON object only, matching this JSON schema:\n"
        f"{json.dumps(json_schema)}"
    )
    if p.system_role:
        messages = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": user},
        ]
    else:
        messages = [{"role": "user", "content": f"{instructions}\n\n---\n\n{user}"}]
    extra = {"response_format": {"type": "json_object"}} if p.json_mode else {}
    for attempt in range(2):
        res = client.chat.completions.create(
            model=p.model, messages=messages, temperature=0.2, max_tokens=4096, **extra
        )
        text = res.choices[0].message.content or ""
        try:
            return schema.model_validate_json(_strip_fences(text))
        except ValidationError as e:
            if attempt == 1:
                raise
            messages += [
                {"role": "assistant", "content": text},
                {
                    "role": "user",
                    "content": f"That JSON is invalid: {e}. Send corrected JSON only.",
                },
            ]
    raise AssertionError("unreachable")


def _strip_fences(text: str) -> str:
    """Some models wrap JSON in ```json fences even in JSON mode."""
    t = text.strip()
    if not t.startswith("```") and "{" in t and not t.startswith("{"):
        t = t[t.index("{") : t.rindex("}") + 1]  # models without JSON mode add chatter
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    return t.strip()


def structured[T: BaseModel](
    system: str, user: str, schema: type[T], chain_names: str | None = None
) -> T:
    """Ask the first working provider for JSON that matches `schema`.

    chain_names picks another provider list (e.g. the quick filter's Gemini). If none of
    those is configured, the main LLM_PROVIDERS chain is used instead.
    """
    pool_key = chain_names or settings.llm_providers
    chain = (providers(chain_names) if chain_names else []) or providers()
    if not chain:
        raise LLMNotConfigured("No LLM provider configured (see LLM_PROVIDERS in .env)")
    errors = []
    for p in rotation_order(pool_key, chain):
        try:
            result = _ask(p, system, user, schema)
            log.info("llm ok provider=%s model=%s schema=%s", p.name, p.model, schema.__name__)
            return result
        except Exception as e:
            wait = cooldown_seconds(e)
            if wait:
                _rest(p, wait)
                log.warning("llm rate limited provider=%s resting %ss", p.name, wait)
            else:
                log.warning("llm failed provider=%s error=%s", p.name, str(e)[:300])
            errors.append(f"{p.name}: {str(e)[:200]}")
    raise LLMFailed("; ".join(errors))
