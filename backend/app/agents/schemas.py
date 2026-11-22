"""Output schemas for every LLM call. One model per agent step.

The LLM must return JSON that validates against these. Anything else is retried once,
then the step hands off to a person (see llm.structured).
Field descriptions are sent to the model as part of the JSON schema, so they are written
as instructions.
"""

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]
Voice = Literal["peer_founder", "numbers_operator", "finance_peer", "short_plain"]

# ---------- 1. Search agent ----------


class Candidate(BaseModel):
    name: str = Field(description="Brand name as written in the tool result")
    domain: str = Field(description="Bare domain, e.g. fernhillgoods.com. No https, no path")
    source_url: str = Field(description="URL where you saw this brand")
    snippet: str = Field(default="", description="Short text from the result about the brand")


class CandidateList(BaseModel):
    """Brands pulled out of ONE tool result."""

    candidates: list[Candidate] = Field(default_factory=list)


Tool = Literal["search_web", "search_form_d", "read_app_reviews", "check_store", "finish"]


class SearchStep(BaseModel):
    """One step of the search agent: pick a tool, and keep brands seen in earlier results."""

    thought: str = Field(description="One sentence: why this tool and these keywords")
    tool: Tool
    query: str | None = Field(default=None, description="search_web / search_form_d keywords")
    app: str | None = Field(default=None, description="read_app_reviews: app handle")
    page: int | None = Field(default=None, description="read_app_reviews: page number")
    domain: str | None = Field(default=None, description="check_store: bare domain")
    new_candidates: list[Candidate] = Field(
        default_factory=list,
        description="Brands from the PREVIOUS results that fit and have a domain",
    )


# ---------- 2. Quick filter ----------


class QuickVerdict(BaseModel):
    domain: str
    keep: bool = Field(description="False only if clearly not a fit. When unsure, true")
    reason: str = Field(description="One short sentence a sales person understands")


class QuickFilterResult(BaseModel):
    verdicts: list[QuickVerdict]


# ---------- 3. Researcher ----------

Signal = Literal[
    "hiring_finance_or_ops",
    "recent_funding",
    "wholesale",
    "multi_channel",
    "international",
    "fast_growth",
    "uses_3pl",
]


class Fact(BaseModel):
    claim: str = Field(description="Plain-English fact about the company, one sentence")
    quote: str = Field(description="EXACT text copied from the page that proves the claim")
    url: str = Field(description="The page URL the quote was copied from")
    signal: Signal | None = Field(default=None, description="Bookkeeping signal, if any")


class ResearchResult(BaseModel):
    summary: str = Field(description="Two sentences: what they sell and how they sell it")
    platform: str | None = Field(default=None, description="e.g. Shopify. Null if unknown")
    channels: list[str] = Field(description="Sales channels backed by a fact, e.g. Amazon")
    facts: list[Fact]


# ---------- 4. Qualifier ----------

Band = Literal["under_1m", "1m_10m", "over_10m", "unknown"]
StaffBand = Literal["under_5", "5_50", "over_50", "unknown"]


class Reason(BaseModel):
    text: str = Field(description="One sentence, plain English")
    points: int = Field(ge=-40, le=40, description="Positive for a fit, negative against")
    evidence_ids: list[int] = Field(description="Ids from EVIDENCE that back this reason")


class QualifyResult(BaseModel):
    reasons_for: list[Reason]
    reasons_against: list[Reason]
    revenue_band: Band
    revenue_confidence: Confidence
    staff_band: StaffBand
    staff_confidence: Confidence
    confidence: float = Field(ge=0, le=1, description="How sure you are about the verdict")
    summary: str = Field(description="One sentence for the sales team: why yes or why no")


# ---------- 5. Contact finder ----------


class Person(BaseModel):
    name: str
    title: str
    quote: str = Field(description="EXACT text from the page that names this person + title")
    url: str


class PeopleResult(BaseModel):
    people: list[Person] = Field(description="Founders, COO/ops leads, finance leads only")


# ---------- 6. Email writer ----------


class FollowUpAngle(BaseModel):
    step: int = Field(ge=1, le=3)
    angle: str = Field(description="The one new idea this follow-up adds")
    evidence_id: int | None = Field(default=None, description="Evidence id if it uses a fact")


class Strategy(BaseModel):
    voice: Voice
    trigger_evidence_id: int = Field(description="The one fact the first email opens with")
    pain: str = Field(description="The bookkeeping problem we think they have, one sentence")
    follow_up_angles: list[FollowUpAngle] = Field(min_length=3, max_length=3)
    avoid: list[str] = Field(description="Things not to mention for this company")


class FirstEmail(BaseModel):
    strategy: Strategy
    subject: str = Field(description="2-5 words, lowercase, specific to them")
    body: str = Field(description="Plain text with [n] markers. 50-90 words. No signature")
    citations: list[int] = Field(description="Evidence ids in marker order: [1] is first")
    confidence: Confidence
    handoff_reason: str | None = Field(default=None, description="Set if a person should write")


class FollowUp(BaseModel):
    body: str = Field(description="Plain text with [n] markers. 25-60 words. No signature")
    citations: list[int]
    confidence: Confidence
    handoff_reason: str | None = None


class SentenceCheck(BaseModel):
    sentence: str
    supported: bool = Field(description="True if the cited quote (or Ledgerwise facts) prove it")
    problem: str | None = Field(default=None, description="What is unsupported, if anything")


class FactCheckResult(BaseModel):
    sentences: list[SentenceCheck]


# ---------- 7. Reply agent + thread report ----------


class ThreadReport(BaseModel):
    interest: Literal["high", "medium", "low", "none"]
    pain: str | None = Field(default=None, description="What hurts for them, in their words")
    objections: list[str]
    next_step: str = Field(description="What should happen next, one sentence")
    new_since_last: list[str] = Field(description="What changed since the last report")
    call_prep: list[str] | None = Field(
        default=None, description="Only when a call is booked: 3-5 bullets for the caller"
    )


# ---------- 8. Compose assistant ----------


class Rewrite(BaseModel):
    body: str = Field(description="The rewritten email, plain text, no signature")
    what_changed: str = Field(description="One sentence: what you changed and why")
