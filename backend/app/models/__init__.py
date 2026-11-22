"""All database tables. One file so the whole data model is readable in one place."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Campaign(Base):
    """One search for a type of brand. Settings come from the New campaign form."""

    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    # {"categories": [...], "channels": [...], "revenue_min": 1, "revenue_max": 10,
    #  "staff_min": 5, "staff_max": 50, "location": "US", "signals": [...], "roles": [...],
    #  "voice": "auto", "target": 30}
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    # draft | running | done | stopped | failed
    status: Mapped[str] = mapped_column(String(16), default="running")
    stage: Mapped[str] = mapped_column(String(32), default="")  # search | filter | research ...
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")  # plain-English status line
    created_by: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Rejection(Base):
    """A company the agents did not go with: at which step and why."""

    __tablename__ = "rejections"
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    domain: Mapped[str] = mapped_column(String(255))
    # code_check | quick_filter | research | qualifier | contact | writer
    stage: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True)
    location: Mapped[str] = mapped_column(String(255), default="")  # "Portland, ME"
    channels: Mapped[list] = mapped_column(JSON, default=list)  # ["Shopify", "Amazon"]
    found_via: Mapped[str] = mapped_column(Text, default="")  # search query or source
    revenue_confidence: Mapped[str] = mapped_column(String(16), default="")
    employee_confidence: Mapped[str] = mapped_column(String(16), default="")
    name: Mapped[str] = mapped_column(String(255))
    domain: Mapped[str] = mapped_column(String(255), unique=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    platform: Mapped[str] = mapped_column(String(64), default="")  # e.g. "shopify"
    revenue_band: Mapped[str] = mapped_column(String(64), default="")  # e.g. "$1-10M (est.)"
    employee_band: Mapped[str] = mapped_column(String(64), default="")  # e.g. "11-50"
    # new -> qualified | disqualified -> contacted -> meeting | suppressed
    status: Mapped[str] = mapped_column(String(32), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    evidence: Mapped[list["Evidence"]] = relationship(back_populates="company")
    contacts: Mapped[list["Contact"]] = relationship(back_populates="company")
    qualifications: Mapped[list["Qualification"]] = relationship(back_populates="company")


class Evidence(Base):
    """One sourced fact. Rule 2: the agent may only state facts that point to a row here."""

    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    claim: Mapped[str] = mapped_column(Text)  # our short paraphrase
    quote: Mapped[str] = mapped_column(Text)  # exact text from the source
    url: Mapped[str] = mapped_column(String(1000))
    source_type: Mapped[str] = mapped_column(String(32))  # website | sec_form_d | job_post | news
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    company: Mapped[Company] = relationship(back_populates="evidence")


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(String(1000), default="")

    company: Mapped[Company] = relationship(back_populates="contacts")


class Qualification(Base):
    __tablename__ = "qualifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    score: Mapped[int] = mapped_column(Integer)  # 0-100
    verdict: Mapped[str] = mapped_column(String(16))  # good | maybe | poor
    # [{"text": "...", "points": 20, "evidence_ids": [1, 2]}]
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    company: Mapped[Company] = relationship(back_populates="qualifications")


class Draft(Base):
    """A first email waiting for a human: pending -> approved (sent) | rejected."""

    __tablename__ = "drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)  # uses [1], [2] markers
    citations: Mapped[list] = mapped_column(JSON, default=list)  # evidence ids, in marker order
    checks: Mapped[list] = mapped_column(JSON, default=list)  # [{"name", "passed", "detail"}]
    # The outreach plan the human approves with the first email (schemas.Strategy).
    strategy: Mapped[dict] = mapped_column(JSON, default=dict)
    handoff_reason: Mapped[str] = mapped_column(Text, default="")  # set if the writer was unsure
    status: Mapped[str] = mapped_column(String(16), default="pending")
    reviewer_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    company: Mapped[Company] = relationship()
    contact: Mapped[Contact] = relationship()


class Thread(Base):
    __tablename__ = "threads"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    subject: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(16), default="agent")  # agent | human
    # open | needs_human | booked | closed | suppressed
    status: Mapped[str] = mapped_column(String(16), default="open")
    handoff_reason: Mapped[str] = mapped_column(Text, default="")
    strategy: Mapped[dict] = mapped_column(JSON, default=dict)  # approved with the first email
    report: Mapped[dict] = mapped_column(JSON, default=dict)  # schemas.ThreadReport
    human_touched: Mapped[bool] = mapped_column(Boolean, default=False)  # a person wrote here
    followups_sent: Mapped[int] = mapped_column(Integer, default=0)
    next_followup_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    company: Mapped[Company] = relationship()
    contact: Mapped[Contact] = relationship()
    messages: Mapped[list["Message"]] = relationship(
        back_populates="thread", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"))
    direction: Mapped[str] = mapped_column(String(16))  # outbound | inbound
    author: Mapped[str] = mapped_column(String(255))  # "agent", a user's email, or the prospect
    body: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(String(255), default="")
    # first | follow_up | reply | manual | confirmation | inbound
    kind: Mapped[str] = mapped_column(String(16), default="reply")
    sent_to: Mapped[str] = mapped_column(String(255), default="")  # where it really went (demo)
    # For agent replies: what the agent decided and why (shown in the UI).
    agent_notes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    thread: Mapped[Thread] = relationship(back_populates="messages")


class Suppression(Base):
    """Rule 3: anyone here is never contacted again."""

    __tablename__ = "suppressions"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Meeting(Base):
    __tablename__ = "meetings"
    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    calendar_ref: Mapped[str] = mapped_column(String(255), default="")  # Cal.com booking uid
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    company: Mapped[Company] = relationship()


class AuditEvent(Base):
    """Every agent and human action lands here."""

    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(255))  # "agent" or a user's email
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AgentRun(Base):
    """A background job (sourcing, research). The UI polls this for progress."""

    __tablename__ = "agent_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="running")  # running | done | failed
    progress: Mapped[str] = mapped_column(Text, default="")
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Setting(Base):
    """Key/value settings the sales team can change in the UI (e.g. autonomy)."""

    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AppSetting(Base):
    """Small key/value settings changed from the app (e.g. test mode email)."""

    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
