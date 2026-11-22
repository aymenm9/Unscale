"""Thread report: rewritten by the reply agent's LLM at the end of every round."""

import json
import logging

from app.agents import llm
from app.agents.prompts import THREAD_REPORT
from app.agents.schemas import ThreadReport
from app.config import settings
from app.models import Thread

log = logging.getLogger(__name__)


def update_report(thread: Thread, booked_label: str | None = None) -> None:
    """Rewrite thread.report. On any LLM failure the old report stays (never blocks a reply)."""
    evidence = "\n".join(f"[{e.id}] {e.claim}" for e in thread.company.evidence)
    history = "\n\n".join(f"[{m.direction} / {m.author}] {m.body}" for m in thread.messages)
    user = (
        f"Company: {thread.company.name}. Contact: {thread.contact.name}, {thread.contact.title}\n"
        f"Call booked: {booked_label or 'no'}\n"
        f"PREVIOUS REPORT: {json.dumps(thread.report or {})}\n\n"
        f"EVIDENCE:\n<page>\n{evidence}\n</page>\n\n<thread>\n{history}\n</thread>"
    )
    try:
        report = llm.structured(THREAD_REPORT, user, ThreadReport, chain_names=settings.llm_judge)
    except Exception as e:
        log.info("report not updated for thread %s: %s", thread.id, e)
        return
    thread.report = report.model_dump()
