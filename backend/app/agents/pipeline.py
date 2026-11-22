"""The campaign pipeline: one LangGraph graph from campaign settings to drafts for review.

  search -> code_checks -> quick_filter -> research -> qualify -> contacts -> write -> END

Each node reads and writes the database, updates the campaign's progress line (the UI
polls it), and writes a Rejection row for every company it drops, with the reason.
The graph runs in a background thread; a "Stop" click is checked between companies.
"""

import difflib
import logging
from datetime import UTC, datetime
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.agents import contacts, llm, qualifier, quick_filter, researcher, search
from app.guards.research import ToolBudget
from app.guards.sending import domain_of
from app.models import (
    Campaign,
    Company,
    Contact,
    Draft,
    Evidence,
    Qualification,
    Rejection,
    Suppression,
)
from app.services.drafts import write_draft
from app.tools import shopify

log = logging.getLogger(__name__)

BAND_LABEL = {
    "under_1m": "Under $1M",
    "1m_10m": "$1M to $10M",
    "over_10m": "Over $10M",
    "unknown": "Unknown",
    "under_5": "Under 5",
    "5_50": "5 to 50",
    "over_50": "Over 50",
}


class State(TypedDict, total=False):
    campaign_id: int
    candidates: list[dict]  # {name, domain, source_url, snippet, store}
    company_ids: list[int]
    pages: dict  # company_id -> {url: text}, kept in memory for the contact finder
    stopped: bool


class Stopped(Exception):
    pass


def _progress(db: Session, c: Campaign, stage: str, done: int, total: int, msg: str) -> None:
    c.stage, c.progress_done, c.progress_total, c.message = stage, done, total, msg
    db.commit()


def _check_stop(db: Session, c: Campaign) -> None:
    db.refresh(c)
    if c.status == "stopped":
        raise Stopped()


def _reject(
    db: Session,
    c: Campaign,
    name: str,
    domain: str,
    stage: str,
    reason: str,
    company_id: int | None = None,
) -> None:
    db.add(
        Rejection(
            campaign_id=c.id,
            company_id=company_id,
            name=name,
            domain=domain,
            stage=stage,
            reason=reason,
        )
    )


def _names_match(a: str, b: str) -> bool:
    a, b = a.lower().strip(), b.lower().strip()
    return bool(a and b) and (a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() > 0.6)


def build(db: Session):
    """Build the graph with the DB session the nodes should use."""

    def campaign(state: State) -> Campaign:
        return db.get(Campaign, state["campaign_id"])

    def search_node(state: State) -> State:
        c = campaign(state)
        target = int(c.settings.get("target", 30))
        _progress(db, c, "search", 0, target * 3, "Searching for brands that fit.")

        def on_step(text: str, n: int) -> None:
            _check_stop(db, c)  # Stop works during the search too
            _progress(db, c, "search", n, target * 3, f"Searching. Last step: {text}")

        found, steps = search.find_candidates(c.settings, target * 3, ToolBudget(), on_step)
        audit.log(db, "agent", "search_done", "campaign", c.id, steps=steps, found=len(found))
        _progress(db, c, "search", len(found), target * 3, f"Found {len(found)} possible brands.")
        return {"candidates": [x.model_dump() for x in found]}

    def code_checks(state: State) -> State:
        c = campaign(state)
        known = set(db.scalars(select(Company.domain)))
        blocked = {s.email.lstrip("@") for s in db.scalars(select(Suppression))}
        blocked_domains = {domain_of(e) for e in blocked} | blocked
        kept = []
        cands = state["candidates"]
        for i, cand in enumerate(cands):
            _check_stop(db, c)
            _progress(db, c, "check", i, len(cands), f"Checking {cand['name']} is a US store.")
            d = cand["domain"]
            if d in known:
                _reject(db, c, cand["name"], d, "code_check", "Already in our list.")
                continue
            if d in blocked_domains:
                _reject(db, c, cand["name"], d, "code_check", "On the do-not-contact list.")
                continue
            store = shopify.check_store(d)
            if not store:
                _reject(
                    db, c, cand["name"], d, "code_check", "Not a Shopify store (no store data)."
                )
                continue
            if store["country"] not in ("US", "United States"):
                _reject(
                    db,
                    c,
                    cand["name"],
                    d,
                    "code_check",
                    f"Store is outside the US ({store['country'] or 'unknown'}).",
                )
                continue
            if not 10 <= store["products"] <= 2000:
                _reject(
                    db,
                    c,
                    cand["name"],
                    d,
                    "code_check",
                    f"{store['products']} products: outside the 10 to 2,000 range.",
                )
                continue
            if not _names_match(cand["name"], store["name"]) and not _names_match(
                cand["name"].replace(" ", ""), d.split(".")[0]
            ):
                _reject(
                    db,
                    c,
                    cand["name"],
                    d,
                    "code_check",
                    f"Store name '{store['name']}' does not match.",
                )
                continue
            kept.append({**cand, "store": store})
            known.add(d)
        db.commit()
        return {"candidates": kept}

    def quick_filter_node(state: State) -> State:
        c = campaign(state)
        cands = state["candidates"]
        _progress(db, c, "filter", 0, len(cands), "Quick filter: dropping clear misses.")
        rows = [
            {
                "domain": x["domain"],
                "name": x["name"],
                "snippet": x.get("snippet", "")[:300],
                "store": {k: x["store"][k] for k in ("city", "province", "products")},
            }
            for x in cands
        ]
        verdicts = quick_filter.run(c.settings, rows)
        kept = []
        for x in cands:
            keep, reason = verdicts.get(x["domain"], (True, ""))
            if keep:
                kept.append(x)
            else:
                _reject(db, c, x["name"], x["domain"], "quick_filter", reason)
        db.commit()
        limit = int(int(c.settings.get("target", 30)) * 1.5)
        return {"candidates": kept[:limit]}

    def research_node(state: State) -> State:
        c = campaign(state)
        cands = state["candidates"]
        ids, pages_by_company = [], {}
        for i, x in enumerate(cands):
            _check_stop(db, c)
            _progress(db, c, "research", i, len(cands), f"Reading {x['name']}'s website.")
            try:
                result, dropped, pages = researcher.research(x["domain"], x["name"], x["store"])
            except Exception as e:
                if llm.is_down(e):
                    raise  # no AI at all: stop the campaign, do not reject every company
                _reject(db, c, x["name"], x["domain"], "research", f"Research failed: {e}")
                db.commit()
                continue
            if len(result.facts) < 2:
                _reject(
                    db,
                    c,
                    x["name"],
                    x["domain"],
                    "research",
                    f"Only {len(result.facts)} facts could be proven from its pages.",
                )
                db.commit()
                continue
            store = x["store"]
            company = Company(
                name=x["name"],
                domain=x["domain"],
                campaign_id=c.id,
                summary=result.summary,
                platform=result.platform or "Shopify",
                channels=result.channels,
                location=", ".join(p for p in (store["city"], store["province"]) if p),
                found_via=x.get("source_url", ""),
                status="new",
            )
            db.add(company)
            db.flush()
            db.add(
                Evidence(
                    company_id=company.id,
                    claim=f"Shopify store with {store['products']} products",
                    quote=f'"published_products_count":{store["products"]}',
                    url=store["url"],
                    source_type="store_data",
                )
            )
            for f in result.facts:
                source = "news" if x["domain"] not in f.url else "website"
                db.add(
                    Evidence(
                        company_id=company.id,
                        claim=f.claim,
                        quote=f.quote,
                        url=f.url,
                        source_type=source,
                    )
                )
            audit.log(
                db,
                "agent",
                "researched",
                "company",
                company.id,
                facts=len(result.facts),
                dropped=[why for _, why in dropped],
            )
            db.commit()
            ids.append(company.id)
            pages_by_company[company.id] = pages
        return {"company_ids": ids, "pages": pages_by_company}

    def qualify_node(state: State) -> State:
        c = campaign(state)
        good = []
        for i, cid in enumerate(state["company_ids"]):
            _check_stop(db, c)
            company = db.get(Company, cid)
            _progress(db, c, "qualify", i, len(state["company_ids"]), f"Scoring {company.name}.")
            evidence = [
                {"id": e.id, "claim": e.claim, "quote": e.quote, "url": e.url}
                for e in company.evidence
            ]
            try:
                q = qualifier.qualify(c.settings, company.name, evidence)
            except Exception as e:
                if llm.is_down(e):
                    raise  # no AI at all: stop the campaign, do not reject every company
                _reject(
                    db, c, company.name, company.domain, "qualifier", f"Scoring failed: {e}", cid
                )
                company.status = "disqualified"
                db.commit()
                continue
            db.add(
                Qualification(
                    company_id=cid,
                    score=q["score"],
                    verdict=q["verdict"],
                    reasons=q["reasons"],
                    confidence=q["confidence"],
                    summary=q["summary"],
                )
            )
            company.revenue_band = BAND_LABEL[q["revenue_band"]]
            company.revenue_confidence = q["revenue_confidence"]
            company.employee_band = BAND_LABEL[q["staff_band"]]
            company.employee_confidence = q["staff_confidence"]
            if q["verdict"] == "poor":
                company.status = "disqualified"
                _reject(db, c, company.name, company.domain, "qualifier", q["summary"], cid)
            else:
                company.status = "qualified"
                if q["verdict"] == "good":
                    good.append(cid)
            audit.log(
                db, "agent", "qualified", "company", cid, score=q["score"], verdict=q["verdict"]
            )
            db.commit()
        return {"company_ids": good}

    def contacts_node(state: State) -> State:
        c = campaign(state)
        with_contact = []
        roles = c.settings.get("roles") or []
        for i, cid in enumerate(state["company_ids"]):
            _check_stop(db, c)
            company = db.get(Company, cid)
            _progress(
                db,
                c,
                "contacts",
                i,
                len(state["company_ids"]),
                f"Finding the right person at {company.name}.",
            )
            try:
                found = contacts.find_contact(company.domain, state["pages"].get(cid, {}), roles)
            except Exception as e:  # a failed lookup drops this company, not the campaign
                log.warning("contact lookup failed for %s: %s", company.domain, e)
                found = None
            if not found:
                _reject(
                    db,
                    c,
                    company.name,
                    company.domain,
                    "contact",
                    "No named person or published email on its pages.",
                    cid,
                )
                db.commit()
                continue
            db.add(
                Contact(
                    company_id=cid,
                    name=found["name"],
                    title=found["title"],
                    email=found["email"],
                    source_url=found["source_url"],
                )
            )
            db.commit()
            with_contact.append(cid)
        return {"company_ids": with_contact}

    def write_node(state: State) -> State:
        c = campaign(state)
        for i, cid in enumerate(state["company_ids"]):
            _check_stop(db, c)
            company = db.get(Company, cid)
            contact = company.contacts[-1]
            _progress(
                db,
                c,
                "write",
                i,
                len(state["company_ids"]),
                f"Writing the first email to {company.name}.",
            )
            try:
                write_draft(db, company, contact)
            except Exception as e:
                db.rollback()
                if llm.is_down(e):
                    raise  # no AI at all: stop the campaign, do not reject every company
                _reject(db, c, company.name, company.domain, "writer", f"Writer failed: {e}", cid)
                db.commit()
                continue
            db.commit()
        return {}

    g = StateGraph(State)
    for name, fn in [
        ("search", search_node),
        ("code_checks", code_checks),
        ("quick_filter", quick_filter_node),
        ("research", research_node),
        ("qualify", qualify_node),
        ("contacts", contacts_node),
        ("write", write_node),
    ]:
        g.add_node(name, fn)
    g.set_entry_point("search")
    g.add_edge("search", "code_checks")
    g.add_edge("code_checks", "quick_filter")
    g.add_edge("quick_filter", "research")
    g.add_edge("research", "qualify")
    g.add_edge("qualify", "contacts")
    g.add_edge("contacts", "write")
    g.add_edge("write", END)
    return g.compile()


def run_campaign(campaign_id: int, session_factory) -> None:
    """Entry point for the background thread."""
    db = session_factory()
    c = db.get(Campaign, campaign_id)
    try:
        build(db).invoke({"campaign_id": campaign_id})
        c.status = "done"
        drafts = db.scalar(
            select(Draft.id)
            .join(Company, Draft.company_id == Company.id)
            .where(Company.campaign_id == campaign_id)
            .limit(1)
        )
        c.message = (
            "Done. First emails are waiting in Approve drafts."
            if drafts
            else ("Done. No company passed every step; see Not chosen.")
        )
    except Stopped:
        c.message = "Stopped by a person."
    except Exception as e:
        log.exception("campaign %s failed", campaign_id)
        c.status = "failed"
        if llm.is_down(e):
            c.message = f"Stopped, the AI is unavailable. {llm.user_message(e)}"
        else:
            c.message = f"Stopped because of an error: {e}"
    c.finished_at = datetime.now(UTC)
    audit.log(db, "agent", f"campaign_{c.status}", "campaign", c.id, message=c.message)
    db.commit()
    db.close()
