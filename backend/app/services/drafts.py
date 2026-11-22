"""Write (or rewrite) the first-email draft for a company. Used by the campaign pipeline's
writer step and by the "Ask the agent to redo" button."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.agents import writer
from app.models import Campaign, Company, Contact, Draft, Suppression


def write_draft(
    db: Session, company: Company, contact: Contact, draft: Draft | None = None
) -> Draft:
    """Run the writer. Updates `draft` in place when given, else adds a new one. Caller commits."""
    suppressed = {s.email for s in db.scalars(select(Suppression))}
    campaign = db.get(Campaign, company.campaign_id) if company.campaign_id else None
    evidence = [{"id": e.id, "claim": e.claim, "quote": e.quote} for e in company.evidence]
    d = writer.write_first(
        company.name,
        {"name": contact.name, "title": contact.title, "email": contact.email},
        evidence,
        campaign.settings if campaign else {},
        suppressed,
    )
    if draft is None:
        draft = Draft(company_id=company.id, contact_id=contact.id)
        db.add(draft)
    draft.subject = d["subject"]
    draft.body = d["body"]
    draft.citations = d["citations"]
    draft.checks = d["checks"]
    draft.strategy = d["strategy"]
    draft.handoff_reason = d["handoff_reason"]
    db.flush()
    audit.log(
        db,
        "agent",
        "draft_written",
        "draft",
        draft.id,
        passed=all(x["passed"] for x in d["checks"]),
    )
    return draft
