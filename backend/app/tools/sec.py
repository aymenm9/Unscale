"""SEC EDGAR full-text search for Form D filings (private fundraises). Free, no key.

SEC requires a User-Agent with contact info (settings.sec_user_agent).
"""

import json
import re
from datetime import date, timedelta
from urllib.parse import quote

from app.tools import http


def search_form_d(keywords: str, months: int = 18, limit: int = 15) -> list[dict]:
    """Form D filings mentioning the keywords. Returns [{name, state, filed, url, cik}]."""
    end = date.today()
    start = end - timedelta(days=30 * months)
    url = (
        "https://efts.sec.gov/LATEST/search-index?q="
        + quote(f'"{keywords}"')
        + f"&forms=D&dateRange=custom&startdt={start}&enddt={end}"
    )
    status, text = http.get(url, check_robots=False)
    if status != 200:
        return []
    try:
        hits = json.loads(text).get("hits", {}).get("hits", [])
    except ValueError:
        return []
    out = []
    for h in hits[:limit]:
        src = h.get("_source", {})
        names = src.get("display_names") or [""]
        name = re.sub(r"\s*\(CIK.*\)$", "", names[0]).strip()
        cik = (src.get("ciks") or [""])[0].lstrip("0")
        adsh = (src.get("adsh") or "").replace("-", "")
        out.append(
            {
                "name": name,
                "state": (src.get("biz_states") or [""])[0],
                "filed": src.get("file_date", ""),
                "cik": cik,
                "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh}/primary_doc.xml",
            }
        )
    return out


def form_d_details(url: str) -> str | None:
    """The filing XML as text (industry, revenue range, offering amount, people)."""
    status, text = http.get(url, check_robots=False)
    return text[:6000] if status == 200 else None
