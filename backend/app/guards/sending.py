"""The last check before any email leaves the app. Used by send_email() only.

Returns a list of reasons NOT to send. Empty list = OK to send.
"""

from datetime import datetime, timedelta

CLOSED_STATUSES = {"suppressed", "closed"}
MIN_GAP = timedelta(hours=24)
DEFAULT_DAILY_CAP = 50


def domain_of(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower().strip()


def is_suppressed(email: str, suppressed_emails: set[str], suppressed_domains: set[str]) -> bool:
    e = email.lower().strip()
    return e in suppressed_emails or domain_of(e) in suppressed_domains


def send_blockers(
    real_recipient: str,
    suppressed_emails: set[str],
    suppressed_domains: set[str],
    thread_status: str | None,
    thread_mode: str | None,
    is_automatic: bool,
    last_sent_to_recipient: datetime | None,
    sent_today: int,
    now: datetime,
    answering_inbound: bool = False,
    daily_cap: int = DEFAULT_DAILY_CAP,
) -> list[str]:
    """is_automatic: sent by an agent or the follow-up timer (not typed by a person).
    answering_inbound: this email answers a reply they just sent, so the 24h gap does not apply.
    """
    blockers = []
    if is_suppressed(real_recipient, suppressed_emails, suppressed_domains):
        blockers.append("Recipient is on the do-not-contact list.")
    if thread_status in CLOSED_STATUSES:
        blockers.append(f"Thread is {thread_status}.")
    if is_automatic and thread_status == "booked":
        blockers.append("A call is booked; automatic emails stop.")
    if is_automatic and thread_mode == "human":
        blockers.append("A person owns this thread; the agent waits until it is handed back.")
    unsolicited = is_automatic and not answering_inbound
    if unsolicited and last_sent_to_recipient and now - last_sent_to_recipient < MIN_GAP:
        blockers.append("Already emailed this person in the last 24 hours.")
    if sent_today >= daily_cap:
        blockers.append(f"Daily sending cap reached ({daily_cap}).")
    return blockers
