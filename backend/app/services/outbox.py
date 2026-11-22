"""The ONLY way an email leaves the app. Agents, the follow-up timer and people all call
send_email().

Before sending: do-not-contact list, thread state, 24h gap, daily cap (guards.sending),
plus the draft checks the caller already ran. Then: strip [n] markers, add the signature,
postal address and unsubscribe link, send through Resend (if a key is set) to the DEMO
inbox only, store the message and write the audit log.
"""

import hashlib
import hmac
import html
import logging
from datetime import UTC, datetime, timedelta

import resend
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.config import settings
from app.guards import outbound_recipient
from app.guards.email import strip_markers
from app.guards.sending import send_blockers
from app.models import Message, Suppression, Thread
from app.services import app_settings

log = logging.getLogger(__name__)


class SendBlocked(Exception):
    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


# ---------- unsubscribe links ----------


def unsubscribe_token(thread_id: int) -> str:
    sig = hmac.new(settings.secret_key.encode(), str(thread_id).encode(), hashlib.sha256)
    return f"{thread_id}.{sig.hexdigest()[:24]}"


def thread_from_token(token: str) -> int | None:
    thread_id, _, _ = token.partition(".")
    if thread_id.isdigit() and hmac.compare_digest(token, unsubscribe_token(int(thread_id))):
        return int(thread_id)
    return None


def unsubscribe_url(thread_id: int) -> str:
    return f"{settings.public_api_url}/api/u/{unsubscribe_token(thread_id)}"


def reply_to(thread_id: int) -> str | None:
    if not settings.resend_inbound_domain:
        return None
    return f"reply+{thread_id}@{settings.resend_inbound_domain}"


# ---------- rendering ----------


BRAND_YELLOW = "#FFC600"
BRAND_INK = "#111111"
BRAND_PAPER = "#F3F3F1"
BRAND_CREAM = "#FFF7D6"
FONT = "Archivo,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def render(body: str, thread_id: int | None) -> tuple[str, str]:
    """(plain text, html) exactly as the prospect sees it.

    Ledgerwise branding in the app's palette (yellow top rule, wordmark, signature card,
    black footer) built from text and colour only: no images, no tracking pixel
    (research/EMAIL_STYLE.md section 3). Tables + inline styles so Gmail/Outlook render it.
    """
    clean = strip_markers(body).strip()
    unsub = unsubscribe_url(thread_id) if thread_id else "#"
    text = (
        f"{clean}\n\n{settings.sender_name}\nBookkeeping for e-commerce brands\n"
        f"{settings.postal_address}\n\n"
        f'Not relevant? Reply "stop" or unsubscribe: {unsub}'
    )
    paras = "".join(
        f'<p style="margin:0 0 14px;">{html.escape(p).replace(chr(10), "<br>")}</p>'
        for p in clean.split("\n\n")
    )
    name = html.escape(settings.sender_name)
    address = html.escape(settings.postal_address)
    body_html = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light"></head>
<body style="margin:0;padding:0;background:{BRAND_PAPER};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
 style="background:{BRAND_PAPER};"><tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
 style="max-width:580px;background:#ffffff;border-top:6px solid {BRAND_YELLOW};
 font-family:{FONT};font-size:15px;line-height:1.6;color:{BRAND_INK};">
<tr><td style="padding:20px 32px 0;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td style="font-size:17px;font-weight:800;letter-spacing:-0.2px;color:{BRAND_INK};">
<span style="display:inline-block;width:10px;height:10px;background:{BRAND_YELLOW};
 margin-right:8px;vertical-align:middle;"></span>Ledgerwise</td>
<td align="right" style="font-size:12px;color:#6b6b6b;">Bookkeeping for e-commerce brands</td>
</tr></table>
<div style="height:1px;background:#ececec;margin-top:16px;font-size:0;line-height:0;">&nbsp;</div>
</td></tr>
<tr><td style="padding:22px 32px 4px;">{paras}</td></tr>
<tr><td style="padding:6px 32px 28px;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="background:{BRAND_CREAM};">
<tr><td style="width:5px;background:{BRAND_YELLOW};font-size:0;line-height:0;">&nbsp;</td>
<td style="padding:12px 18px 12px 14px;">
<div style="font-weight:700;font-size:15px;color:{BRAND_INK};">{name}</div>
<div style="font-size:13px;color:#444444;">Bookkeeping, payouts and sales tax for online stores</div>
</td></tr></table>
</td></tr>
<tr><td style="background:{BRAND_INK};padding:16px 32px;font-size:12px;line-height:1.6;color:#bdbdbd;">
<span style="color:#ffffff;">{address}</span><br>
Not relevant? Reply "stop" or
<a href="{unsub}" style="color:{BRAND_YELLOW};text-decoration:underline;">unsubscribe</a>.
</td></tr>
</table></td></tr></table></body></html>"""
    return text, body_html


# ---------- sending ----------


def _suppression_sets(db: Session) -> tuple[set[str], set[str]]:
    entries = [s.email.lower() for s in db.scalars(select(Suppression))]
    return {e for e in entries if not e.startswith("@")}, {
        e[1:] for e in entries if e.startswith("@")
    }


def blockers_for(
    db: Session,
    thread: Thread,
    is_automatic: bool,
    answering_inbound: bool,
    now: datetime | None = None,
) -> list[str]:
    now = now or datetime.now(UTC)
    emails, domains = _suppression_sets(db)
    last = db.scalar(
        select(func.max(Message.created_at)).where(
            Message.thread_id == thread.id, Message.direction == "outbound"
        )
    )
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    day_start = now - timedelta(hours=24)
    sent_today = (
        db.scalar(
            select(func.count(Message.id)).where(
                Message.direction == "outbound", Message.created_at >= day_start
            )
        )
        or 0
    )
    return send_blockers(
        thread.contact.email,
        emails,
        domains,
        thread.status,
        thread.mode,
        is_automatic,
        last,
        sent_today,
        now,
        answering_inbound=answering_inbound,
        daily_cap=settings.daily_send_cap,
    )


def send_email(
    db: Session,
    thread: Thread,
    body: str,
    kind: str,
    author: str,
    is_automatic: bool,
    answering_inbound: bool = False,
    notes: dict | None = None,
    subject: str | None = None,
) -> Message:
    """Send one email in a thread, or raise SendBlocked. Caller commits."""
    reasons = blockers_for(db, thread, is_automatic, answering_inbound)
    if reasons:
        audit.log(db, author, "send_blocked", "thread", thread.id, kind=kind, reasons=reasons)
        raise SendBlocked(reasons)

    subject = subject or (thread.subject if kind == "first" else f"Re: {thread.subject}")
    text, body_html = render(body, thread.id)
    to = outbound_recipient(thread.contact.email, app_settings.test_email(db))
    if settings.resend_api_key:
        resend.api_key = settings.resend_api_key
        payload = {
            "from": settings.resend_from,
            "to": [to],
            "subject": subject,
            "text": text,
            "html": body_html,
            "headers": {
                "List-Unsubscribe": f"<{unsubscribe_url(thread.id)}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
        }
        if reply_to(thread.id):
            payload["reply_to"] = reply_to(thread.id)
        try:
            resend.Emails.send(payload)
        except Exception as e:  # provider refused or is down: nothing is stored as sent
            audit.log(db, author, "send_failed", "thread", thread.id, kind=kind, error=str(e)[:300])
            raise SendBlocked([f"The email service refused it: {e}"]) from e
    else:
        log.info("Email not sent (no RESEND_API_KEY). to=%s subject=%s", to, subject)

    msg = Message(
        thread_id=thread.id,
        direction="outbound",
        author=author,
        body=strip_markers(body),
        subject=subject,
        kind=kind,
        sent_to=to,
        agent_notes=notes,
    )
    db.add(msg)
    thread.updated_at = datetime.now(UTC)
    if not is_automatic and kind != "first":  # approving the first email is not "writing here"
        thread.human_touched = True
    audit.log(db, author, f"email_sent_{kind}", "thread", thread.id, sent_to=to)
    return msg
