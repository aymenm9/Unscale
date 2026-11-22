"""Contact finder (last node): the right person and an email, only for "good" companies.

Order: people named on the brand's pages (LLM extracts, code verifies the quote), then an
address published on the site, then a first-name pattern, then Hunter if a key is set.
Remember: outbound mail still only goes to the demo inbox.
"""

import re

from app.agents import llm
from app.agents.prompts import CONTACT_FINDER
from app.agents.schemas import PeopleResult, Person
from app.config import settings
from app.guards.research import keep_sourced
from app.tools import hunter

ROLE_ORDER = [
    ("founder", ["founder", "owner", "ceo"]),
    ("ops", ["coo", "operations", "ops", "general manager"]),
    ("finance", ["cfo", "finance", "controller", "accounting"]),
]


def _rank(person: Person, roles: list[str]) -> int:
    title = person.title.lower()
    for i, (role, words) in enumerate(ROLE_ORDER):
        if any(w in title for w in words) and (not roles or role in roles):
            return i
    return 99


def published_email(domain: str, pages: dict[str, str]) -> str | None:
    found = re.findall(r"[a-z0-9._%+-]+@" + re.escape(domain), " ".join(pages.values()).lower())
    for prefix in ("hello", "info", "contact", "team", "support"):
        for e in found:
            if e.startswith(prefix + "@"):
                return e
    return found[0] if found else None


def find_contact(domain: str, pages: dict[str, str], roles: list[str]) -> dict | None:
    """{name, title, email, email_confidence, source_url} or None."""
    person = None
    if pages:
        text = "\n\n".join(f'<page url="{u}">\n{t}\n</page>' for u, t in pages.items())
        try:
            people = llm.structured(
                CONTACT_FINDER, text, PeopleResult, chain_names=settings.llm_read
            ).people
        except Exception:
            people = []
        kept, _ = keep_sourced(people, pages)
        ranked = sorted((p for p in kept if _rank(p, roles) < 99), key=lambda p: _rank(p, roles))
        person = ranked[0] if ranked else None

    site_email = published_email(domain, pages)
    if person:
        first, _, last = person.name.partition(" ")
        hit = hunter.find_email(domain, first, last)
        if hit:
            email, conf = hit[0], "high" if hit[1] >= 80 else "medium"
        elif site_email:
            email, conf = site_email, "medium"
        else:
            email, conf = f"{first.lower()}@{domain}", "low"
        return {
            "name": person.name,
            "title": person.title,
            "email": email,
            "email_confidence": conf,
            "source_url": person.url,
        }
    if site_email:
        return {
            "name": "",
            "title": "Team inbox",
            "email": site_email,
            "email_confidence": "medium",
            "source_url": f"https://{domain}",
        }
    return None
