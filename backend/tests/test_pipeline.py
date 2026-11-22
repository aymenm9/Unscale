"""The whole campaign pipeline with fake tools and a fake LLM: free and deterministic."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents import contacts, llm, pipeline, researcher, search
from app.agents.schemas import (
    Candidate,
    CandidateList,
    FactCheckResult,
    FirstEmail,
    PeopleResult,
    Person,
    QualifyResult,
    QuickFilterResult,
    QuickVerdict,
    Reason,
    ResearchResult,
    SearchStep,
    SentenceCheck,
    Strategy,
)
from app.agents.schemas import Fact as FactModel
from app.db import Base
from app.models import Campaign, Company, Draft, Rejection

PAGES = {
    "good.com": "Good Candle Co makes hand-poured soy candles in Austin, Texas. "
    "Now on Amazon and in 40 boutiques through our new wholesale program. "
    "Meet the team: Ana Ruiz, Co-founder and COO, runs operations. Email hello@good.com",
    "thin.com": "Welcome to Thin Shop.",
}
STORES = {
    "good.com": {
        "name": "Good Candle Co",
        "city": "Austin",
        "province": "Texas",
        "country": "US",
        "products": 140,
        "currency": "USD",
        "ships_to": ["US"],
        "url": "https://good.com/meta.json",
    },
    "thin.com": {
        "name": "Thin Shop",
        "city": "",
        "province": "",
        "country": "US",
        "products": 50,
        "currency": "USD",
        "ships_to": ["US"],
        "url": "https://thin.com/meta.json",
    },
    "canada.com": {
        "name": "Canada Goods",
        "city": "",
        "province": "",
        "country": "CA",
        "products": 50,
        "currency": "CAD",
        "ships_to": ["CA"],
        "url": "https://canada.com/meta.json",
    },
    "agency.com": {
        "name": "Agency Co",
        "city": "",
        "province": "",
        "country": "US",
        "products": 30,
        "currency": "USD",
        "ships_to": ["US"],
        "url": "https://agency.com/meta.json",
    },
}

GOOD_BODY = (
    "Hi Ana, saw Good Candle Co just started selling wholesale to boutiques [1]. That usually "
    "means invoices, net-30 terms and Shopify payouts all landing in the same books. Ledgerwise "
    "does the monthly bookkeeping for growing e-commerce brands, so busy founders can stop "
    "reconciling at night. Worth a short call to see if it fits?"
)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)
    return session


def fake_world(monkeypatch, *, invented: bool = False):
    """Fake every tool and the LLM. Returns the list of schemas the LLM was asked for."""
    asked = []
    search_calls = {"n": 0}

    def structured(system, user, schema, chain_names=None):
        asked.append(schema.__name__)
        if schema is SearchStep:
            search_calls["n"] += 1
            if search_calls["n"] == 1:
                return SearchStep(thought="look", tool="search_web", query="candle brands")
            cands = [
                Candidate(name=STORES[d]["name"], domain=d, source_url=f"https://{d}")
                for d in ("good.com", "thin.com", "canada.com", "agency.com")
            ]
            if invented:
                cands.append(Candidate(name="Ghost", domain="ghost.com", source_url="x"))
            return SearchStep(thought="done", tool="finish", new_candidates=cands)
        if schema is CandidateList:
            return CandidateList()  # the step itself lists candidates in these fakes
        if schema is QuickFilterResult:
            return QuickFilterResult(
                verdicts=[
                    QuickVerdict(domain="agency.com", keep=False, reason="An agency, not a store."),
                ]
            )
        if schema is ResearchResult:
            domain = "good.com" if "good.com" in user else "thin.com"
            facts = [
                FactModel(
                    claim="Sells wholesale",
                    quote="in 40 boutiques through our new wholesale program",
                    url=f"https://{domain}",
                    signal="wholesale",
                ),
                FactModel(claim="Sells on Amazon", quote="Now on Amazon", url=f"https://{domain}"),
                FactModel(
                    claim="Raised $9M", quote="raised $9M last year", url=f"https://{domain}"
                ),
            ]
            return ResearchResult(
                summary="Candles.", platform="Shopify", channels=["Amazon"], facts=facts
            )
        if schema is QualifyResult:
            ids = [int(x) for x in __import__("re").findall(r"\[(\d+)\]", user)]
            return QualifyResult(
                reasons_for=[
                    Reason(text="Wholesale", points=20, evidence_ids=[ids[1]]),
                    Reason(text="Invented", points=30, evidence_ids=[999]),
                ],
                reasons_against=[],
                revenue_band="1m_10m",
                revenue_confidence="low",
                staff_band="5_50",
                staff_confidence="low",
                confidence=0.9,
                summary="Good fit.",
            )
        if schema is PeopleResult:
            return PeopleResult(
                people=[
                    Person(
                        name="Ana Ruiz",
                        title="Co-founder and COO",
                        quote="Ana Ruiz, Co-founder and COO",
                        url="https://good.com",
                    )
                ]
            )
        if schema is FirstEmail:
            ids = [int(x) for x in __import__("re").findall(r"id (\d+):", user)]
            return FirstEmail(
                strategy=Strategy(
                    voice="numbers_operator",
                    trigger_evidence_id=ids[1],
                    pain="Payouts.",
                    avoid=[],
                    follow_up_angles=[
                        {"step": 1, "angle": "a"},
                        {"step": 2, "angle": "b"},
                        {"step": 3, "angle": "c", "evidence_id": 999},
                    ],
                ),
                subject="wholesale at good candle",
                body=GOOD_BODY,
                citations=[ids[1]],
                confidence="high",
            )
        if schema is FactCheckResult:
            return FactCheckResult(sentences=[SentenceCheck(sentence="x", supported=True)])
        raise AssertionError(schema)

    monkeypatch.setattr(llm, "structured", structured)
    monkeypatch.setattr(
        search.web,
        "search",
        lambda q, max_results=8: [
            {"title": f"{STORES[d]['name']}", "url": f"https://{d}", "snippet": "store"}
            for d in STORES
        ],
    )
    monkeypatch.setattr(pipeline.shopify, "check_store", lambda d: STORES.get(d))

    def fetch(domain, name):
        return {f"https://{domain}": PAGES[domain]} if domain in PAGES else {}

    monkeypatch.setattr(researcher, "fetch_pages", fetch)
    monkeypatch.setattr(contacts.hunter, "find_email", lambda *a: None)
    return asked


def start(db, target=5):
    s = db()
    c = Campaign(name="Test", settings={"target": target, "roles": []}, status="running")
    s.add(c)
    s.commit()
    return c.id


def test_pipeline_end_to_end(db, monkeypatch):
    fake_world(monkeypatch)
    cid = start(db)
    pipeline.run_campaign(cid, db)

    s = db()
    c = s.get(Campaign, cid)
    assert c.status == "done", c.message
    rejections = {r.domain: (r.stage, r.reason) for r in s.scalars(select(Rejection))}
    assert rejections["canada.com"][0] == "code_check"
    assert rejections["agency.com"] == ("quick_filter", "An agency, not a store.")

    good = s.scalar(select(Company).where(Company.domain == "good.com"))
    # The invented "$9M" quote is not on the page, so it was dropped.
    assert not any("9M" in e.claim for e in good.evidence)
    q = good.qualifications[-1]
    assert q.verdict == "good" and q.score == 70  # the uncited +30 reason was removed
    assert good.contacts[-1].name == "Ana Ruiz"
    assert good.contacts[-1].email == "hello@good.com"

    draft = s.scalar(select(Draft).where(Draft.company_id == good.id))
    assert all(ch["passed"] for ch in draft.checks), draft.checks
    assert draft.strategy["follow_up_angles"][2]["evidence_id"] is None  # unknown id cleared


def test_thin_company_is_rejected_at_research(db, monkeypatch):
    fake_world(monkeypatch)
    cid = start(db)
    pipeline.run_campaign(cid, db)
    s = db()
    stages = {r.domain: r.stage for r in s.scalars(select(Rejection))}
    assert stages["thin.com"] == "research"


def test_invented_candidate_is_ignored(db, monkeypatch):
    fake_world(monkeypatch, invented=True)
    found, log = search.find_candidates({}, 10, search.ToolBudget())
    assert "ghost.com" not in [c.domain for c in found]
    assert any("Ghost" in line for line in log)


def test_stop_halts_the_run(db, monkeypatch):
    fake_world(monkeypatch)
    cid = start(db)
    real = pipeline.shopify.check_store

    def stop_then_check(d):
        s = db()
        s.get(Campaign, cid).status = "stopped"
        s.commit()
        return real(d)

    monkeypatch.setattr(pipeline.shopify, "check_store", stop_then_check)
    pipeline.run_campaign(cid, db)
    c = db().get(Campaign, cid)
    assert c.status == "stopped" and "Stopped" in c.message


def test_llm_failure_marks_campaign_failed_not_crash(db, monkeypatch):
    def broken(*a, **k):
        raise llm.LLMNotConfigured("no key")

    monkeypatch.setattr(llm, "structured", broken)
    cid = start(db)
    pipeline.run_campaign(cid, db)
    c = db().get(Campaign, cid)
    # Not "done, nothing found": the team is told the AI is unavailable and why.
    assert c.status == "failed"
    assert "AI is unavailable" in c.message and "not set up" in c.message


def test_ai_limits_stop_the_campaign_instead_of_rejecting_everyone(db, monkeypatch):
    fake_world(monkeypatch)
    real = llm.structured

    def limits_hit_at_scoring(system, user, schema, **k):
        if schema.__name__ == "QualifyResult":
            raise llm.LLMFailed("groq: 429", rate_limited=True, retry_in=600)
        return real(system, user, schema, **k)

    monkeypatch.setattr(llm, "structured", limits_hit_at_scoring)
    cid = start(db)
    pipeline.run_campaign(cid, db)
    s = db()
    c = s.get(Campaign, cid)
    assert c.status == "failed"
    assert "used up their limits" in c.message and "about 10 minutes" in c.message
    assert not any(r.stage == "qualifier" for r in s.scalars(select(Rejection)))


def test_tool_timeout_does_not_stop_search(db, monkeypatch):
    fake_world(monkeypatch)
    calls = {"n": 0}

    def flaky(q, max_results=8):
        calls["n"] += 1
        raise search.httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(search.web, "search", flaky)
    _found, log = search.find_candidates({}, 10, search.ToolBudget())
    assert calls["n"] == 1  # the agent got an error message and moved on
    assert any("Finished" in line for line in log)


def test_extraction_finds_brands_and_repeats_are_blocked(monkeypatch):
    calls = {"search": 0, "steps": 0}

    def structured(system, user, schema, chain_names=None):
        if schema is SearchStep:
            calls["steps"] += 1
            # the model keeps asking for the same search; code must not rerun it
            return SearchStep(thought="look", tool="search_web", query="candles")
        if schema is CandidateList:
            if "Good Candle Co" in user:
                return CandidateList(
                    candidates=[Candidate(name="Good Candle Co", domain="good.com", source_url="u")]
                )
            return CandidateList()
        raise AssertionError(schema)

    def fake_search(q, max_results=8):
        calls["search"] += 1
        return [{"title": "Good Candle Co", "url": "https://good.com", "snippet": "candles"}]

    monkeypatch.setattr(llm, "structured", structured)
    monkeypatch.setattr(search.web, "search", fake_search)
    found, log = search.find_candidates({}, 10, search.ToolBudget())
    assert [c.domain for c in found] == ["good.com"]  # pulled out by the extraction call
    assert calls["search"] == 1  # the repeated query never hit the API again
    assert any("in a row found nothing new" in line for line in log)  # stall stop
    assert calls["steps"] == 1 + search.MAX_STEPS_WITHOUT_NEW
