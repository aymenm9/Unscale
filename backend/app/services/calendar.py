"""Free call slots and booking.

Today: slots come from fixed business hours minus meetings already booked in our DB.
Next: swap `free_slots` / `book` for Cal.com API v2 (GET /v2/slots, POST /v2/bookings)
once CALCOM_API_KEY is set, so slots come from the sales team's real calendar.
"""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Meeting

ET = ZoneInfo("America/New_York")
SLOT_TIMES = [time(10, 0), time(11, 30), time(14, 0), time(15, 30)]
CALL_MINUTES = 30


def label(slot: datetime) -> str:
    """'Tue Nov 24, 10:00 AM ET'"""
    return slot.astimezone(ET).strftime("%a %b %-d, %-I:%M %p ET")


def free_slots(db: Session, count: int = 3, now: datetime | None = None) -> list[datetime]:
    now = now or datetime.now(UTC)
    booked = {
        m.start_at.replace(tzinfo=UTC) if m.start_at.tzinfo is None else m.start_at
        for m in db.scalars(select(Meeting)).all()
    }
    slots: list[datetime] = []
    day = now.astimezone(ET).date() + timedelta(days=1)  # never offer same-day
    while len(slots) < count:
        if day.weekday() < 5:
            for t in SLOT_TIMES:
                start = datetime.combine(day, t, tzinfo=ET).astimezone(UTC)
                if start not in booked and len(slots) < count:
                    slots.append(start)
        day += timedelta(days=1)
    return slots


def book(db: Session, thread_id: int, company_id: int, start: datetime) -> Meeting:
    meeting = Meeting(
        thread_id=thread_id,
        company_id=company_id,
        start_at=start,
        end_at=start + timedelta(minutes=CALL_MINUTES),
        calendar_ref="local",
    )
    db.add(meeting)
    return meeting
