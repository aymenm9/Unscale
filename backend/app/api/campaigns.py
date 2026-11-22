"""Campaigns (start a search, follow it, see every company it found or dropped) and Home."""

import re
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app import db as app_db
from app.agents import pipeline
from app.api.routes import company_row, company_step, thread_row
from app.auth import current_user
from app.config import settings as app_config
from app.db import get_db
from app.models import Campaign, Company, Draft, Meeting, Message, Rejection, Thread, User
from app.services import app_settings, calendar

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])


class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    categories: list[str] = []
    channels: list[str] = []
    revenue_min: int = 1
    revenue_max: int = 10
    staff_min: int = 5
    staff_max: int = 50
    location: str = "Anywhere in the US"
    signals: list[str] = []
    roles: list[str] = ["founder", "ops", "finance"]
    voice: str = "auto"
    target: int = Field(default=30, ge=5, le=60)


def _stats(db: Session, campaign_id: int) -> dict:
    companies = db.scalars(select(Company).where(Company.campaign_id == campaign_id)).all()
    ids = [c.id for c in companies]
    rejected = (
        db.scalar(
            select(func.count(Rejection.id)).where(
                Rejection.campaign_id == campaign_id, Rejection.company_id.is_(None)
            )
        )
        or 0
    )
    threads = db.scalars(select(Thread).where(Thread.company_id.in_(ids))).all() if ids else []
    verdicts = [c.qualifications[-1].verdict for c in companies if c.qualifications]
    return {
        "found": len(companies) + rejected,
        "researched": len(companies),
        "good": verdicts.count("good"),
        "maybe": verdicts.count("maybe"),
        "poor": verdicts.count("poor"),
        "drafts": db.scalar(
            select(func.count(Draft.id)).where(Draft.company_id.in_(ids), Draft.status == "pending")
        )
        if ids
        else 0,
        "emailed": len(threads),
        "replies": sum(1 for t in threads if any(m.direction == "inbound" for m in t.messages)),
        "calls": sum(1 for t in threads if t.status == "booked"),
    }


def campaign_json(db: Session, c: Campaign) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "settings": c.settings,
        "status": c.status,
        "stage": c.stage,
        "progress_done": c.progress_done,
        "progress_total": c.progress_total,
        "message": c.message,
        "created_at": c.created_at,
        "finished_at": c.finished_at,
        "stats": _stats(db, c.id),
    }


def _run_in_background(campaign_id: int) -> None:
    pipeline.run_campaign(campaign_id, app_db.SessionLocal)


@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    return [campaign_json(db, c) for c in db.scalars(select(Campaign).order_by(Campaign.id.desc()))]


def unique_name(db: Session, name: str) -> str:
    """Every campaign gets its own title: 'Candles', then 'Candles (2)', 'Candles (3)'."""
    base = re.sub(r" \(\d+\)$", "", name.strip()) or "Campaign"
    taken = set(db.scalars(select(Campaign.name)))
    if base not in taken:
        return base
    n = 2
    while f"{base} ({n})" in taken:
        n += 1
    return f"{base} ({n})"


def _launch(db: Session, tasks: BackgroundTasks, user: User, name: str, settings: dict) -> dict:
    """Create a campaign and start its search in the background. One at a time."""
    running = db.scalar(select(Campaign).where(Campaign.status == "running"))
    if running:
        raise HTTPException(409, f"'{running.name}' is still running. Stop it or wait.")
    c = Campaign(
        name=unique_name(db, name),
        settings=settings,
        status="running",
        created_by=user.email,
        message="Starting.",
    )
    db.add(c)
    db.flush()
    audit.log(db, user.email, "campaign_started", "campaign", c.id, settings=settings)
    db.commit()
    tasks.add_task(_run_in_background, c.id)
    return campaign_json(db, c)


@router.post("/campaigns")
def start_campaign(
    body: CampaignIn,
    tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return _launch(db, tasks, user, body.name, body.model_dump(exclude={"name"}))


@router.post("/campaigns/{campaign_id}/rerun")
def rerun_campaign(
    campaign_id: int,
    tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Run the same search again (same settings). Brands already found are skipped."""
    old = db.get(Campaign, campaign_id)
    if not old:
        raise HTTPException(404, "Not found")
    return _launch(db, tasks, user, old.name, dict(old.settings))


@router.get("/test-mode")
def get_test_mode(db: Session = Depends(get_db), user: User = Depends(current_user)):
    email = app_settings.test_email(db)
    return {"on": bool(email), "email": email, "demo_inbox": app_config.demo_inbox}


class TestModeIn(BaseModel):
    email: str = Field(default="", max_length=255)


@router.put("/test-mode")
def set_test_mode(
    body: TestModeIn, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    """Turn test mode on (an email) or off (empty). Every email then goes to that inbox."""
    email = body.email.strip().lower()
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(422, "That does not look like an email address.")
    app_settings.put(db, app_settings.TEST_EMAIL, email)
    audit.log(db, user.email, "test_mode_on" if email else "test_mode_off", "settings", 0)
    db.commit()
    return get_test_mode(db, user)


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    c = db.get(Campaign, campaign_id)
    if not c:
        raise HTTPException(404, "Not found")
    companies = db.scalars(select(Company).where(Company.campaign_id == c.id)).all()
    rows = []
    for co in companies:
        draft = db.scalar(select(Draft).where(Draft.company_id == co.id, Draft.status == "pending"))
        thread = db.scalar(select(Thread).where(Thread.company_id == co.id))
        rows.append(
            {
                **company_row(co),
                "step": company_step(db, co),
                "draft_id": draft.id if draft else None,
                "thread_id": thread.id if thread else None,
                "needs_you": bool(thread and thread.status == "needs_human"),
            }
        )
    rows.sort(key=lambda r: r["score"] or -1, reverse=True)
    rejections = db.scalars(
        select(Rejection).where(Rejection.campaign_id == c.id).order_by(Rejection.id)
    )
    return {
        **campaign_json(db, c),
        "companies": rows,
        "rejections": [
            {
                "id": r.id,
                "name": r.name,
                "domain": r.domain,
                "stage": r.stage,
                "reason": r.reason,
                "company_id": r.company_id,
            }
            for r in rejections
        ],
    }


@router.post("/campaigns/{campaign_id}/stop")
def stop_campaign(
    campaign_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    c = db.get(Campaign, campaign_id)
    if not c:
        raise HTTPException(404, "Not found")
    if c.status == "running":
        c.status = "stopped"
        c.message = "Stopping after the current company."
        audit.log(db, user.email, "campaign_stopped", "campaign", c.id)
        db.commit()
    return campaign_json(db, c)


@router.get("/home")
def home(db: Session = Depends(get_db), user: User = Depends(current_user)):
    threads = db.scalars(select(Thread).order_by(Thread.updated_at.desc())).all()
    drafts = db.scalars(select(Draft).where(Draft.status == "pending").order_by(Draft.created_at))
    running = db.scalar(select(Campaign).where(Campaign.status == "running"))
    meeting = db.scalar(
        select(Meeting).where(Meeting.start_at >= datetime.now(UTC)).order_by(Meeting.start_at)
    )
    waiting = [
        {
            "kind": "reply",
            "id": t.id,
            "company": t.company.name,
            "why": t.handoff_reason,
            "when": t.updated_at,
        }
        for t in threads
        if t.status == "needs_human"
    ] + [
        {
            "kind": "draft",
            "id": d.id,
            "company": d.company.name,
            "why": f"First email ready, fit {d.company.qualifications[-1].score}"
            if d.company.qualifications
            else "First email ready",
            "when": d.created_at,
        }
        for d in drafts
    ]
    companies = db.scalars(select(Company)).all()
    verdicts = [c.qualifications[-1].verdict for c in companies if c.qualifications]
    return {
        "user": user.name,
        "stats": {
            "found": len(companies),
            "good": verdicts.count("good"),
            "emailed": len(threads),
            "replies": sum(1 for t in threads if any(m.direction == "inbound" for m in t.messages)),
            "calls": sum(1 for t in threads if t.status == "booked"),
            "sent_emails": db.scalar(
                select(func.count(Message.id)).where(Message.direction == "outbound")
            )
            or 0,
        },
        "running": campaign_json(db, running) if running else None,
        "waiting": waiting,
        "pipeline": [thread_row(t) for t in threads[:8]],
        "next_meeting": {
            "label": calendar.label(meeting.start_at),
            "company": meeting.company.name,
            "thread_id": meeting.thread_id,
        }
        if meeting
        else None,
    }
