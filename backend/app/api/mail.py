"""Compose (templates, AI rewrite, preview), the test inbox, follow-ups, unsubscribe links
and the Resend inbound webhook."""

import logging
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.agents import writer
from app.agents.templates import TEMPLATES
from app.auth import current_user
from app.config import settings
from app.db import get_db
from app.guards.email import check_email
from app.models import Message, Suppression, Thread, User
from app.services import calendar
from app.services.followups import run_due, send_followup
from app.services.outbox import render, thread_from_token
from app.services.replies import handle_inbound

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])
public = APIRouter(prefix="/api")


def _thread(db: Session, thread_id: int) -> Thread:
    t = db.get(Thread, thread_id)
    if not t:
        raise HTTPException(404, "Not found")
    return t


# ---------- compose ----------


@router.get("/threads/{thread_id}/templates")
def templates(thread_id: int, db: Session = Depends(get_db)):
    t = _thread(db, thread_id)
    first = (t.contact.name or "there").split(" ")[0]
    slots = ", ".join(calendar.label(s) for s in calendar.free_slots(db))
    return [
        {
            "key": k,
            "label": k.replace("_", " ").capitalize(),
            "body": v.format(first_name=first, slots=slots),
        }
        for k, v in TEMPLATES.items()
    ]


class RewriteIn(BaseModel):
    body: str
    comment: str


@router.post("/threads/{thread_id}/rewrite")
def rewrite(
    thread_id: int,
    body: RewriteIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    t = _thread(db, thread_id)
    evidence = "\n".join(f'[{e.id}] {e.claim} (quote: "{e.quote}")' for e in t.company.evidence)
    history = "\n\n".join(f"[{m.direction} / {m.author}] {m.body}" for m in t.messages)
    context = (
        f"Company: {t.company.name}. Contact: {t.contact.name}, {t.contact.title}\n"
        f"APPROVED STRATEGY: {t.strategy}\nREPORT: {t.report}\n"
        f"FREE SLOTS: {[calendar.label(s) for s in calendar.free_slots(db)]}\n\n"
        f"EVIDENCE:\n<page>\n{evidence}\n</page>\n\n<thread>\n{history}\n</thread>"
    )
    try:
        r = writer.rewrite(context, body.body, body.comment)
    except Exception as e:
        raise HTTPException(503, f"The AI could not rewrite this right now: {e}") from e
    suppressed = {s.email for s in db.scalars(select(Suppression))}
    checks = check_email("reply", None, r.body, [], set(), t.contact.email.lower(), suppressed)
    audit.log(db, user.email, "ai_rewrite", "thread", t.id, comment=body.comment)
    db.commit()
    return {"body": r.body, "what_changed": r.what_changed, "checks": checks}


class PreviewIn(BaseModel):
    body: str
    thread_id: int | None = None


@router.post("/preview")
def preview(body: PreviewIn, db: Session = Depends(get_db)):
    text, html = render(body.body, body.thread_id)
    checks = []
    if body.thread_id:
        t = _thread(db, body.thread_id)
        suppressed = {s.email for s in db.scalars(select(Suppression))}
        checks = check_email(
            "reply", None, body.body, [], set(), t.contact.email.lower(), suppressed
        )
    return {"text": text, "html": html, "checks": checks}


# ---------- test inbox ----------


@router.get("/outbox")
def outbox(db: Session = Depends(get_db)):
    msgs = db.scalars(select(Message).order_by(Message.id.desc()).limit(200)).all()
    out = []
    for m in msgs:
        text, html = render(m.body, m.thread_id) if m.direction == "outbound" else (m.body, "")
        out.append(
            {
                "id": m.id,
                "thread_id": m.thread_id,
                "direction": m.direction,
                "kind": m.kind,
                "author": m.author,
                "subject": m.subject or f"Re: {m.thread.subject}",
                "sent_to": m.sent_to,
                "created_at": m.created_at,
                "company": m.thread.company.name,
                "contact": {"name": m.thread.contact.name, "email": m.thread.contact.email},
                "text": text,
                "html": html,
                "thread_status": m.thread.status,
            }
        )
    return out


# ---------- follow-ups ----------


@router.post("/followups/run")
def followups_run(db: Session = Depends(get_db)):
    return {"handled": run_due(db)}


@router.post("/threads/{thread_id}/followup-now")
def followup_now(thread_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Demo button: send the next follow-up now instead of waiting for its day."""
    t = _thread(db, thread_id)
    if t.mode != "agent" or t.status != "open":
        raise HTTPException(409, "Follow-ups only run while the agent owns an open thread.")
    if t.followups_sent >= 3:
        raise HTTPException(409, "All 3 follow-ups were already sent.")
    result = send_followup(db, t, forced=True)
    audit.log(db, user.email, "followup_forced", "thread", t.id, result=result)
    db.commit()
    return {"result": result}


# ---------- public: unsubscribe + inbound webhook ----------

UNSUB_PAGE = (
    "<!doctype html><meta name=viewport content='width=device-width'><body style='font-family:"
    "system-ui;max-width:480px;margin:60px auto;padding:0 16px'><h1>You're unsubscribed</h1>"
    "<p>Ledgerwise will not email you again.</p></body>"
)


@public.api_route("/u/{token}", methods=["GET", "POST"], response_class=HTMLResponse)
def unsubscribe(token: str, db: Session = Depends(get_db)):
    """One-click unsubscribe (RFC 8058 sends POST; a person clicking sends GET)."""
    thread_id = thread_from_token(token)
    t = db.get(Thread, thread_id) if thread_id else None
    if not t:
        raise HTTPException(404, "Unknown link")
    db.merge(Suppression(email=t.contact.email.lower(), reason="Clicked unsubscribe"))
    t.status = "suppressed"
    t.next_followup_at = None
    t.company.status = "suppressed"
    audit.log(db, t.contact.email, "unsubscribed_by_link", "thread", t.id)
    db.commit()
    return UNSUB_PAGE


def _received_body(email_id: str) -> str:
    """Resend's webhook may carry only metadata; fetch the text with the API.
    Endpoint per Resend's 'Received emails' API (verify against current docs on deploy)."""
    if not settings.resend_api_key:
        return ""
    res = httpx.get(
        f"https://api.resend.com/emails/receiving/{email_id}",
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        timeout=20,
    )
    return res.json().get("text", "") if res.status_code == 200 else ""


def strip_quoted(text: str) -> str:
    """Keep only the new part of a reply (drop '> quoted' lines and 'On ... wrote:')."""
    lines = []
    for line in text.splitlines():
        if line.startswith(">") or re.match(r"^On .+wrote:$", line.strip()):
            break
        lines.append(line)
    return "\n".join(lines).strip()


@public.post("/webhooks/resend")
async def resend_inbound(request: Request, token: str = "", db: Session = Depends(get_db)):
    if not settings.webhook_secret or token != settings.webhook_secret:
        raise HTTPException(401, "Bad token")
    payload = await request.json()
    if payload.get("type") != "email.received":
        return {"ignored": payload.get("type")}
    data = payload.get("data", {})
    to = " ".join(data.get("to") or [])
    m = re.search(r"reply\+(\d+)@", to)
    t = db.get(Thread, int(m.group(1))) if m else None
    if not t:
        return {"ignored": "no thread"}
    text = data.get("text") or _received_body(data.get("email_id", ""))
    body = strip_quoted(text)
    if not body:
        return {"ignored": "empty"}
    return handle_inbound(db, t, body)
