"""One polite HTTP client for every tool.

- Honest User-Agent (SEC requires a contact address).
- Max 1 request per second per host (SEC: 5), so we never hammer a site.
- Respects robots.txt.
- Caches responses in memory for 7 days, so a rerun costs nothing.
"""

import logging
import threading
import time
import urllib.robotparser
from urllib.parse import urlparse

import httpx

from app.config import settings

log = logging.getLogger(__name__)

CACHE_SECONDS = 7 * 24 * 3600
_cache: dict[str, tuple[float, int, str]] = {}
_last_hit: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_lock = threading.Lock()


class Blocked(Exception):
    """robots.txt disallows this URL. We do not fetch it."""


def _wait_turn(host: str) -> None:
    gap = 0.2 if host.endswith("sec.gov") else 1.0
    with _lock:
        wait = _last_hit.get(host, 0) + gap - time.monotonic()
        _last_hit[host] = time.monotonic() + max(wait, 0)
    if wait > 0:
        time.sleep(wait)


def _allowed(url: str) -> bool:
    parts = urlparse(url)
    host = parts.netloc
    if host not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            res = httpx.get(
                f"{parts.scheme}://{host}/robots.txt",
                timeout=10,
                headers={"User-Agent": settings.sec_user_agent},
            )
            rp.parse(res.text.splitlines() if res.status_code == 200 else [])
            _robots[host] = rp
        except httpx.HTTPError:
            _robots[host] = None  # no robots.txt reachable: treat as allowed
    rp = _robots[host]
    return rp is None or rp.can_fetch(settings.sec_user_agent, url)


def get(url: str, headers: dict | None = None, check_robots: bool = True) -> tuple[int, str]:
    """GET a URL and return (status, text). Uses the cache and the per-host rate limit."""
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1], hit[2]
    if check_robots and not _allowed(url):
        raise Blocked(f"robots.txt disallows {url}")
    _wait_turn(urlparse(url).netloc)
    h = {"User-Agent": settings.sec_user_agent, **(headers or {})}
    for attempt in range(3):
        try:
            res = httpx.get(url, headers=h, timeout=25, follow_redirects=True)
        except httpx.HTTPError as e:
            log.info("fetch failed %s: %s", url, e)
            if attempt == 2:
                return 0, ""
            time.sleep(2**attempt)
            continue
        if res.status_code in (429, 500, 502, 503) and attempt < 2:
            time.sleep(2 ** (attempt + 1))
            continue
        _cache[url] = (time.time(), res.status_code, res.text)
        return res.status_code, res.text
    return 0, ""


def post_json(url: str, payload: dict, headers: dict) -> dict:
    """POST JSON (search APIs). Not cached: the caller caches by query if needed."""
    _wait_turn(urlparse(url).netloc)
    res = httpx.post(url, json=payload, headers=headers, timeout=30)
    res.raise_for_status()
    return res.json()
