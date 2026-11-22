"""HTTP API used by the web app. Every write is audited."""

import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.auth import COOKIE, current_user, verify_password
from app.db import get_db
from app.guards.email import check_email
from app.models import (
    AuditEvent,
    AuthSession,
    Company,
    Contact,
    Draft,
    Meeting,
    Suppression,
    Thread,
    User,
)
from app.services import calendar
from app.services.drafts import write_draft
from app.services.followups import schedule_next
from app.services.outbox import SendBlocked, send_email
from app.services.replies import handle_inbound

public = APIRouter(prefix="/api")
router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])


# ---------- auth ----------


class LoginIn(BaseModel):
    email: str
    password: str


@public.post("/auth/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    token = secrets.token_hex(32)
    db.add(AuthSession(token=token, user_id=user.id))
    db.commit()
    response.set_cookie(
        COOKIE, token, httponly=True, samesite="lax", secure=False, max_age=60 * 60 * 24 * 14
    )
    return {"email": user.email, "name": user.name}


@public.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"email": user.email, "name": user.name}


# ---------- helpers to shape JSON ----------


def evidence_json(e):
    return {
        "id": e.id,
        "claim": e.claim,
        "quote": e.quote,
        "url": e.url,
        "source_type": e.source_type,
        "fetched_at": e.fetched_at,
    }


def latest_qualification(c: Company):
    if not c.qualifications:
        return None
    q = max(c.qualifications, key=lambda q: q.created_at)
    return {
        "score": q.score,
        "verdict": q.verdict,
        "reasons": q.reasons,
        "confidence": q.confidence,
        "summary": q.summary,
    }


def company_step(db: Session, c: Company) -> int:
    """Where a company is on the 5-stop line: researched, qualified, emailed, replied, booked."""
    if c.status == "meeting":
        return 5
    thread = db.scalar(select(Thread).where(Thread.company_id == c.id))
    if thread:
        return 4 if any(m.direction == "inbound" for m in thread.messages) else 3
    return 2 if c.qualifications else 1


def company_row(c: Company):
    q = latest_qualification(c)
    return {
        "id": c.id,
        "name": c.name,
        "domain": c.domain,
        "status": c.status,
        "platform": c.platform,
        "revenue_band": c.revenue_band,
        "employee_band": c.employee_band,
        "revenue_confidence": c.revenue_confidence,
        "employee_confidence": c.employee_confidence,
        "location": c.location,
        "channels": c.channels or [],
        "campaign_id": c.campaign_id,
        "score": q["score"] if q else None,
        "verdict": q["verdict"] if q else None,
        "why": q["summary"] if q else "",
        "evidence_count": len(c.evidence),
    }


def draft_json(d: Draft):
    by_id = {e.id: e for e in d.company.evidence}
    return {
        "id": d.id,
        "status": d.status,
        "subject": d.subject,
        "body": d.body,
        "checks": d.checks,
        "strategy": d.strategy,
        "handoff_reason": d.handoff_reason,
        "created_at": d.created_at,
        "citations": [evidence_json(by_id[i]) for i in d.citations if i in by_id],
        "company": company_row(d.company),
        "qualification": latest_qualification(d.company),
        "contact": {"name": d.contact.name, "title": d.contact.title, "email": d.contact.email},
    }


def thread_row(t: Thread):
    last = t.messages[-1] if t.messages else None
    replied = any(m.direction == "inbound" for m in t.messages)
    step = 5 if t.status == "booked" else 4 if replied else 3
    return {
        "id": t.id,
        "subject": t.subject,
        "mode": t.mode,
        "status": t.status,
        "handoff_reason": t.handoff_reason,
        "human_touched": t.human_touched,
        "step": step,
        "updated_at": t.updated_at,
        "next_followup_at": t.next_followup_at,
        "followups_sent": t.followups_sent,
        "company": {"id": t.company.id, "name": t.company.name},
        "contact": {"name": t.contact.name, "title": t.contact.title},
        "last_message": {"direction": last.direction, "body": last.body[:160]} if last else None,
    }


# ---------- companies ----------


@router.get("/companies")
def list_companies(db: Session = Depends(get_db)):
    rows = [company_row(c) for c in db.scalars(select(Company)).all()]
    return sorted(rows, key=lambda r: r["score"] or -1, reverse=True)


@router.get("/companies/{company_id}")
def get_company(company_id: int, db: Session = Depends(get_db)):
    c = db.get(Company, company_id) or _404()
    return {
        **company_row(c),
        "summary": c.summary,
        "qualification": latest_qualification(c),
        "evidence": [evidence_json(e) for e in c.evidence],
        "contacts": [
            {
                "id": p.id,
                "name": p.name,
                "title": p.title,
                "email": p.email,
                "source_url": p.source_url,
            }
            for p in c.contacts
        ],
        "drafts": [
            {"id": d.id, "status": d.status, "subject": d.subject}
            for d in db.scalars(select(Draft).where(Draft.company_id == c.id))
        ],
        "threads": [
            thread_row(t) for t in db.scalars(select(Thread).where(Thread.company_id == c.id))
        ],
    }


# ---------- review queue ----------


@router.get("/review")
def review_queue(db: Session = Depends(get_db)):
    drafts = db.scalars(select(Draft).where(Draft.status == "pending").order_by(Draft.created_at))
    return [draft_json(d) for d in drafts]


class ApproveIn(BaseModel):
    subject: str | None = None
    body: str | None = None


def _run_checks(db: Session, d: Draft) -> list[dict]:
    suppressed = {s.email for s in db.scalars(select(Suppression))}
    checks = check_email(
        "first",
        d.subject,
        d.body,
        d.citations,
        {e.id for e in d.company.evidence},
        d.contact.email.lower(),
        suppressed,
    )
    # Keep the fact checker's result from writing time (a person may have edited the body).
    return checks + [c for c in d.checks if c["name"] == "fact_check"]


@router.post("/review/{draft_id}/approve")
def approve(
    draft_id: int,
    body: ApproveIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    d = db.get(Draft, draft_id) or _404()
    if d.status != "pending":
        raise HTTPException(status_code=409, detail=f"Draft is already {d.status}")
    edited = bool(body.subject or body.body)
    d.subject = body.subject or d.subject
    d.body = body.body or d.body
    d.checks = _run_checks(db, d)
    blocking = [
        c for c in d.checks if not c["passed"] and not (edited and c["name"] == "fact_check")
    ]
    if blocking:
        db.commit()
        raise HTTPException(status_code=422, detail={"checks": d.checks})

    now = datetime.now(UTC)
    thread = Thread(
        company_id=d.company_id,
        contact_id=d.contact_id,
        subject=d.subject,
        strategy=d.strategy,
        first_sent_at=now,
    )
    db.add(thread)
    db.flush()
    db.refresh(thread)
    try:
        msg = send_email(db, thread, d.body, "first", user.email, is_automatic=False)
    except SendBlocked as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    schedule_next(thread)
    d.status = "approved"
    d.decided_at = now
    d.company.status = "contacted"
    audit.log(
        db,
        user.email,
        "draft_approved",
        "draft",
        d.id,
        edited=edited,
        sent_to=msg.sent_to,
        strategy=d.strategy,
    )
    db.commit()
    return {"thread_id": thread.id, "sent_to": msg.sent_to}


class RejectIn(BaseModel):
    note: str = ""


@router.post("/review/{draft_id}/redo")
def redo(draft_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Ask the agent to write this draft again (it fixes its own check failures)."""
    d = db.get(Draft, draft_id) or _404()
    if d.status != "pending":
        raise HTTPException(status_code=409, detail=f"Draft is already {d.status}")
    company = db.get(Company, d.company_id)
    contact = db.get(Contact, d.contact_id)
    try:
        write_draft(db, company, contact, draft=d)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=503, detail=f"The agent could not rewrite it now: {e}"
        ) from e
    audit.log(db, user.email, "draft_redo_requested", "draft", d.id)
    db.commit()
    return draft_json(d)


@router.post("/review/{draft_id}/reject")
def reject(
    draft_id: int, body: RejectIn, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    d = db.get(Draft, draft_id) or _404()
    d.status = "rejected"
    d.reviewer_note = body.note
    d.decided_at = datetime.now(UTC)
    audit.log(db, user.email, "draft_rejected", "draft", d.id, note=body.note)
    db.commit()
    return {"ok": True}


# ---------- inbox ----------


@router.get("/threads")
def list_threads(db: Session = Depends(get_db)):
    threads = db.scalars(select(Thread).order_by(Thread.updated_at.desc()))
    return [thread_row(t) for t in threads]


@router.get("/threads/{thread_id}")
def get_thread(thread_id: int, db: Session = Depends(get_db)):
    t = db.get(Thread, thread_id) or _404()
    meeting = db.scalar(select(Meeting).where(Meeting.thread_id == t.id))
    return {
        **thread_row(t),
        "contact": {"name": t.contact.name, "title": t.contact.title, "email": t.contact.email},
        "report": t.report,
        "strategy": t.strategy,
        "evidence": [evidence_json(e) for e in t.company.evidence],
        "qualification": latest_qualification(t.company),
        "messages": [
            {
                "id": m.id,
                "direction": m.direction,
                "author": m.author,
                "body": m.body,
                "subject": m.subject,
                "kind": m.kind,
                "sent_to": m.sent_to,
                "agent_notes": m.agent_notes,
                "created_at": m.created_at,
            }
            for m in t.messages
        ],
        "meeting": {"start_at": meeting.start_at, "label": calendar.label(meeting.start_at)}
        if meeting
        else None,
    }


@router.post("/threads/{thread_id}/takeover")
def takeover(thread_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    t = db.get(Thread, thread_id) or _404()
    t.mode = "human"
    audit.log(db, user.email, "thread_takeover", "thread", t.id)
    db.commit()
    return thread_row(t)


@router.post("/threads/{thread_id}/release")
def release(thread_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    t = db.get(Thread, thread_id) or _404()
    if t.status == "suppressed":
        raise HTTPException(status_code=409, detail="Prospect opted out; the agent cannot resume.")
    t.mode = "agent"
    if t.status == "needs_human":
        t.status = "open"
    t.handoff_reason = ""
    audit.log(db, user.email, "thread_released", "thread", t.id)
    db.commit()
    return thread_row(t)


class SendIn(BaseModel):
    body: str


@router.post("/threads/{thread_id}/send")
def send_manual(
    thread_id: int, body: SendIn, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    t = db.get(Thread, thread_id) or _404()
    suppressed = {s.email for s in db.scalars(select(Suppression))}
    if t.status == "suppressed" or t.contact.email.lower() in suppressed:
        raise HTTPException(status_code=409, detail="Prospect opted out. Do not contact.")
    checks = check_email("reply", None, body.body, [], set(), t.contact.email.lower(), suppressed)
    if not all(c["passed"] for c in checks):
        raise HTTPException(status_code=422, detail={"checks": checks})
    try:
        send_email(db, t, body.body, "manual", user.email, is_automatic=False)
    except SendBlocked as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    t.next_followup_at = None  # a person is talking now; the timer steps back
    t.mode = "human"  # the agent stays quiet until someone clicks Hand back
    db.commit()
    return {"ok": True}


@router.post("/threads/{thread_id}/simulate-reply")
def simulate_reply(thread_id: int, body: SendIn, db: Session = Depends(get_db)):
    """Demo helper: pretend the prospect replied, then run the reply agent on it."""
    t = db.get(Thread, thread_id) or _404()
    return handle_inbound(db, t, body.body)


# ---------- calls, suppressions, audit ----------


@router.get("/meetings")
def list_meetings(db: Session = Depends(get_db)):
    meetings = db.scalars(select(Meeting).order_by(Meeting.start_at))
    return [
        {
            "id": m.id,
            "thread_id": m.thread_id,
            "start_at": m.start_at,
            "label": calendar.label(m.start_at),
            "company": company_row(m.company),
        }
        for m in meetings
    ]


class SuppressIn(BaseModel):
    email: str  # an address, or "@domain.com" for a whole company
    reason: str = "Added by hand"


@router.post("/suppressions")
def add_suppression(
    body: SuppressIn, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    db.merge(Suppression(email=body.email.lower().strip(), reason=body.reason))
    audit.log(db, user.email, "suppression_added", "suppression", 0, email=body.email)
    db.commit()
    return {"ok": True}


@router.get("/suppressions")
def list_suppressions(db: Session = Depends(get_db)):
    return [
        {"email": s.email, "reason": s.reason, "created_at": s.created_at}
        for s in db.scalars(select(Suppression).order_by(Suppression.created_at.desc()))
    ]


@router.get("/audit")
def list_audit(db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(200))
    return [
        {
            "id": a.id,
            "actor": a.actor,
            "action": a.action,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "detail": a.detail,
            "created_at": a.created_at,
        }
        for a in rows
    ]


def _404():
    raise HTTPException(status_code=404, detail="Not found")
