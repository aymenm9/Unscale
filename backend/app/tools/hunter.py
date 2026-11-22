"""Hunter.io free tier (50 credits/month). Used only for top leads, only if a key is set."""

from urllib.parse import quote

import httpx

from app.config import settings


def find_email(domain: str, first: str, last: str) -> tuple[str, int] | None:
    """(email, score 0-100) or None."""
    if not settings.hunter_api_key or not first:
        return None
    url = (
        f"https://api.hunter.io/v2/email-finder?domain={quote(domain)}"
        f"&first_name={quote(first)}&last_name={quote(last)}&api_key={settings.hunter_api_key}"
    )
    try:
        data = httpx.get(url, timeout=20).json().get("data") or {}
    except (httpx.HTTPError, ValueError):
        return None
    return (data["email"], int(data.get("score") or 0)) if data.get("email") else None
