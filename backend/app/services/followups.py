"""Follow-up timer (code, no LLM decisions). Runs every 15 minutes.

Follow-up 1 on day 3, 2 on day 7, 3 on day 11 after the first email, weekdays, 9:30 AM ET.
Each one is written on its due day from the approved strategy, checked, then sent.
Stops for good when they reply, opt out, book, or a person takes over.
"""

import logging
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.agents import writer
from app.models import Suppression, Thread
from app.services.outbox import SendBlocked, send_email

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
DAYS = {1: 3, 2: 7, 3: 11}  # follow-up number -> days after the first email
SEND_AT = time(9, 30)


def due_at(first_sent: datetime, step: int) -> datetime:
    """Day N after the first email, moved to the next weekday, at 9:30 AM ET."""
    day = first_sent.astimezone(ET).date() + timedelta(days=DAYS[step])
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return datetime.combine(day, SEND_AT, tzinfo=ET).astimezone(UTC)


def schedule_next(thread: Thread) -> None:
    step = thread.followups_sent + 1
    thread.next_followup_at = due_at(thread.first_sent_at, step) if step in DAYS else None


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=UTC) if dt is not None and dt.tzinfo is None else dt


def send_followup(db: Session, thread: Thread, forced: bool = False) -> str:
    """Write and send the next follow-up now. Returns what happened, in plain English.

    forced: a person clicked "Send next follow-up now" (demo), so the 24h gap is skipped.
    """
    step = min(thread.followups_sent + 1, 3)
    evidence = [{"id": e.id, "claim": e.claim, "quote": e.quote} for e in thread.company.evidence]
    history = "\n\n".join(f"[{m.direction}] {m.body}" for m in thread.messages)
    suppressed = {s.email for s in db.scalars(select(Suppression))}
    try:
        fu = writer.write_follow_up(
            step, thread.strategy, history, evidence, thread.contact.email.lower(), suppressed
        )
    except Exception as e:
        fu = {"ok": False, "handoff_reason": f"Follow-up writer failed: {e}", "checks": []}
    if not fu["ok"]:
        thread.status, thread.mode = "needs_human", "human"
        thread.handoff_reason = f"Follow-up {step}: {fu['handoff_reason']}"
        thread.next_followup_at = None
        audit.log(db, "agent", "followup_handoff", "thread", thread.id, reason=fu["handoff_reason"])
        return thread.handoff_reason
    try:
        send_email(
            db,
            thread,
            fu["body"],
            "follow_up",
            "agent",
            is_automatic=True,
            answering_inbound=forced,
            notes={"action": "follow_up", "step": step, "checks": fu["checks"]},
        )
    except SendBlocked as e:
        thread.next_followup_at = None
        return f"Blocked: {e}"
    thread.followups_sent = step
    schedule_next(thread)
    return f"Follow-up {step} sent."


def run_due(db: Session, now: datetime | None = None) -> int:
    """Send every follow-up that is due. Returns how many threads were handled."""
    now = now or datetime.now(UTC)
    threads = db.scalars(
        select(Thread).where(
            Thread.mode == "agent",
            Thread.status == "open",
            Thread.next_followup_at.is_not(None),
        )
    ).all()
    handled = 0
    for t in threads:
        if _aware(t.next_followup_at) > now:
            continue
        log.info("follow-up due thread=%s: %s", t.id, send_followup(db, t))
        handled += 1
        db.commit()
    return handled
