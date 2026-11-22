"""Apply the reply agent's decision to the database. All side effects live here."""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app import audit
from app.agents.reply import decide
from app.models import Message, Suppression, Thread
from app.services import calendar
from app.services.outbox import SendBlocked, send_email
from app.services.reports import update_report

CONFIRM_UNSUBSCRIBE = "Understood, you won't hear from us again. Sorry for the interruption."
ET = ZoneInfo("America/New_York")


def _history(thread: Thread) -> str:
    return "\n\n".join(f"[{m.direction} / {m.author}]\n{m.body}" for m in thread.messages)


def _offered_slots(thread: Thread) -> list[datetime]:
    """Slots offered in the most recent agent message, if any."""
    for m in reversed(thread.messages):
        if m.direction == "outbound" and m.agent_notes and m.agent_notes.get("offered_slots"):
            return [datetime.fromisoformat(s) for s in m.agent_notes["offered_slots"]]
    return []


def _handoff(thread: Thread, reason: str) -> None:
    thread.status = "needs_human"
    thread.mode = "human"
    thread.handoff_reason = reason


def _agent_send(db: Session, thread: Thread, body: str, kind: str, notes: dict) -> bool:
    """Agent reply through the email sender. A block becomes a handoff."""
    try:
        send_email(
            db, thread, body, kind, "agent", is_automatic=True, answering_inbound=True, notes=notes
        )
        return True
    except SendBlocked as e:
        _handoff(thread, f"Reply was blocked: {e}")
        return False


def handle_inbound(db: Session, thread: Thread, body: str) -> dict:
    """Store an inbound email, then let the agent act (unless a person owns the thread)."""
    history = _history(thread)  # before adding the new message
    db.add(
        Message(
            thread_id=thread.id,
            direction="inbound",
            author=thread.contact.email,
            body=body,
            kind="inbound",
        )
    )
    thread.updated_at = datetime.now(UTC)
    thread.next_followup_at = None  # any reply stops the follow-ups
    audit.log(db, thread.contact.email, "reply_received", "thread", thread.id)
    db.flush()
    db.refresh(thread)

    if thread.mode == "human" or thread.status in ("suppressed", "closed"):
        update_report(thread)
        db.commit()
        return {"action": "none", "reason": "A person owns this thread."}

    offered = _offered_slots(thread)
    free = calendar.free_slots(db)
    result = decide(
        {
            "inbound": body,
            "history": history,
            "company_name": thread.company.name,
            "contact_name": thread.contact.name,
            "offered_slots": [calendar.label(s) for s in offered],
            "free_slots": [calendar.label(s) for s in free],
            "strategy": str(thread.strategy or ""),
        }
    )
    action = result.get("action", "handoff")
    notes = {
        "action": action,
        "reason": result.get("reason", ""),
        "analysis": result.get("analysis"),
    }
    booked_label = None

    if action == "suppress":
        thread.company.status = "suppressed"
        # The one allowed message after an opt-out: a confirmation. Sent before the
        # suppression row exists, because the sender blocks suppressed addresses.
        try:
            send_email(
                db,
                thread,
                CONFIRM_UNSUBSCRIBE,
                "confirmation",
                "agent",
                is_automatic=False,
                answering_inbound=True,
                notes=notes,
            )
        except SendBlocked:
            pass
        db.merge(Suppression(email=thread.contact.email.lower(), reason=result.get("reason", "")))
        thread.status = "suppressed"
    elif action == "handoff":
        _handoff(thread, result.get("reason", ""))
    elif action == "book":
        start = offered[result["slot_index"]]
        meeting = calendar.book(db, thread.id, thread.company_id, start)
        booked_label = calendar.label(start)
        _agent_send(
            db,
            thread,
            f"Great, you're booked for {booked_label}. A calendar invite is on its way.",
            "confirmation",
            notes,
        )
        thread.status = "booked"
        thread.company.status = "meeting"
        db.flush()
        audit.log(db, "agent", "meeting_booked", "meeting", meeting.id, start=start.isoformat())
    elif action == "send":
        notes["offered_slots"] = [s.isoformat() for s in free]
        if _agent_send(db, thread, result["reply"], "reply", notes):
            check_back = (result.get("analysis") or {}).get("check_back_date")
            if check_back:
                try:
                    day = datetime.fromisoformat(check_back).date()
                    thread.next_followup_at = datetime.combine(
                        day, time(9, 30), tzinfo=ET
                    ).astimezone(UTC)
                except ValueError:
                    pass

    db.flush()
    db.refresh(thread)
    update_report(thread, booked_label)
    audit.log(db, "agent", f"reply_{action}", "thread", thread.id, decision=notes)
    db.commit()
    return notes
