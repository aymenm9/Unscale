"""Email sender, follow-ups, compose, test inbox, unsubscribe link, webhook, campaigns API."""

from datetime import UTC, datetime, timedelta

from app import db as app_db
from app.agents import llm
from app.agents.schemas import FactCheckResult, FollowUp, Rewrite, SentenceCheck
from app.api import campaigns as campaigns_api
from app.config import settings
from app.models import Thread
from app.services import followups, outbox
from app.services.outbox import render, thread_from_token, unsubscribe_token


def approve_first(client):
    draft = client.get("/api/review").json()[0]
    res = client.post(f"/api/review/{draft['id']}/approve", json={})
    assert res.status_code == 200, res.json()
    return res.json()["thread_id"]


def test_approve_stores_strategy_and_schedules_follow_up(client):
    tid = approve_first(client)
    t = client.get(f"/api/threads/{tid}").json()
    assert t["strategy"]["voice"]
    assert t["next_followup_at"] is not None
    assert t["followups_sent"] == 0
    assert t["human_touched"] is False  # approving is not writing in the thread
    first = t["messages"][0]
    assert first["kind"] == "first" and "[1]" not in first["body"]  # markers stripped


def test_rendered_email_has_unsubscribe_and_no_markers():
    text, html = render("Hi Ana [1], worth a call?", 7)
    assert "[1]" not in text and "[1]" not in html
    assert "/api/u/7." in text and "unsubscribe" in html
    assert "<img" not in html


def test_unsubscribe_token_is_signed():
    assert thread_from_token(unsubscribe_token(5)) == 5
    assert thread_from_token("5.forged") is None


def test_unsubscribe_link_suppresses(client):
    tid = approve_first(client)
    res = client.get(f"/api/u/{unsubscribe_token(tid)}")
    assert res.status_code == 200 and "unsubscribed" in res.text
    assert client.get(f"/api/threads/{tid}").json()["status"] == "suppressed"
    assert client.post(f"/api/threads/{tid}/send", json={"body": "hi"}).status_code == 409


def test_manual_send_marks_human_touched_and_stops_timer(client):
    tid = approve_first(client)
    assert (
        client.post(f"/api/threads/{tid}/send", json={"body": "Hi Ana, quick note."}).status_code
        == 200
    )
    t = client.get(f"/api/threads/{tid}").json()
    assert t["human_touched"] is True and t["next_followup_at"] is None
    assert t["mode"] == "human"  # sending by hand is a takeover


def test_manual_send_with_price_is_blocked(client):
    tid = approve_first(client)
    res = client.post(f"/api/threads/{tid}/send", json={"body": "It is $300/month."})
    assert res.status_code == 422


def test_follow_up_due_dates_skip_weekends():
    fri = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)  # Friday
    assert followups.due_at(fri, 1).weekday() == 0  # day 3 is Monday
    assert followups.due_at(fri, 2).date().isoformat() == "2026-11-27"


def fake_follow_up(
    monkeypatch,
    body="Hi Ana, one more thought: wholesale invoices often split "
    "margins from day one. Happy to show how we set that up for brands like yours?",
):
    def structured(system, user, schema, chain_names=None):
        if schema is FollowUp:
            return FollowUp(body=body, citations=[], confidence="high")
        if schema is FactCheckResult:
            return FactCheckResult(sentences=[SentenceCheck(sentence="x", supported=True)])
        raise llm.LLMNotConfigured("not in this test")

    monkeypatch.setattr(llm, "structured", structured)


def test_follow_up_now_sends_and_schedules_next(client, monkeypatch):
    tid = approve_first(client)
    fake_follow_up(monkeypatch)
    res = client.post(f"/api/threads/{tid}/followup-now")
    assert res.json()["result"] == "Follow-up 1 sent."
    t = client.get(f"/api/threads/{tid}").json()
    assert t["followups_sent"] == 1 and t["messages"][-1]["kind"] == "follow_up"


def test_timer_follow_up_blocked_within_24h_of_last_email(client, monkeypatch):
    tid = approve_first(client)
    fake_follow_up(monkeypatch)
    s = next(client.app.dependency_overrides[app_db.get_db]())
    thread = s.get(Thread, tid)
    assert "24 hours" in followups.send_followup(s, thread)  # not forced: the gap applies


def test_bad_follow_up_hands_off(client, monkeypatch):
    tid = approve_first(client)
    fake_follow_up(monkeypatch, body="Just checking in, our plans start at $99/month.")
    client.post(f"/api/threads/{tid}/followup-now")
    t = client.get(f"/api/threads/{tid}").json()
    assert t["status"] == "needs_human" and t["mode"] == "human"


def test_reply_stops_follow_ups(client):
    tid = approve_first(client)
    client.post(f"/api/threads/{tid}/simulate-reply", json={"body": "Tell me more"})
    assert client.get(f"/api/threads/{tid}").json()["next_followup_at"] is None


def test_timer_skips_human_owned_threads(client, monkeypatch):
    tid = approve_first(client)
    client.post(f"/api/threads/{tid}/takeover")
    fake_follow_up(monkeypatch)
    later = datetime.now(UTC) + timedelta(days=30)
    s = next(client.app.dependency_overrides[app_db.get_db]())
    assert followups.run_due(s, now=later) == 0


def test_templates_and_rewrite(client, monkeypatch):
    tid = approve_first(client)
    tpls = client.get(f"/api/threads/{tid}/templates").json()
    assert {"pricing", "has_accountant"} <= {t["key"] for t in tpls}
    assert "$" not in tpls[0]["body"]

    def structured(system, user, schema, chain_names=None):
        assert "COMMENT: warmer" in user and "EVIDENCE" in user  # full details reach the AI
        return Rewrite(body="Hi Ana, thanks so much for the reply!", what_changed="Warmer.")

    monkeypatch.setattr(llm, "structured", structured)
    out = client.post(f"/api/threads/{tid}/rewrite", json={"body": "Hi.", "comment": "warmer"})
    assert out.json()["what_changed"] == "Warmer."


def test_rewrite_without_llm_says_so(client):
    tid = approve_first(client)
    res = client.post(f"/api/threads/{tid}/rewrite", json={"body": "Hi.", "comment": "x"})
    assert res.status_code == 503


def test_outbox_shows_rendered_emails(client):
    approve_first(client)
    mail = client.get("/api/outbox").json()
    assert mail[0]["sent_to"] == "delivered@resend.dev"
    assert "unsubscribe" in mail[0]["html"]


def test_webhook_routes_reply_to_thread(client, monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "s3cret")
    tid = approve_first(client)
    payload = {
        "type": "email.received",
        "data": {
            "to": [f"reply+{tid}@abc.resend.app"],
            "text": "Please unsubscribe me\n\n> old text",
        },
    }
    assert client.post("/api/webhooks/resend?token=bad", json=payload).status_code == 401
    out = client.post("/api/webhooks/resend?token=s3cret", json=payload).json()
    assert out["action"] == "suppress"


def test_campaign_api_starts_background_run(client, monkeypatch):
    started = []
    monkeypatch.setattr(campaigns_api, "_run_in_background", lambda cid: started.append(cid))
    res = client.post("/api/campaigns", json={"name": "Candles", "categories": ["Candles"]})
    assert res.status_code == 200 and started == [res.json()["id"]]
    assert client.post("/api/campaigns", json={"name": "Two"}).status_code == 409
    detail = client.get(f"/api/campaigns/{res.json()['id']}").json()
    assert detail["status"] == "running"
    stopped = client.post(f"/api/campaigns/{res.json()['id']}/stop").json()
    assert stopped["status"] == "stopped"


def test_sample_campaign_lists_companies_and_rejections(client):
    camp = client.get("/api/campaigns").json()[0]
    detail = client.get(f"/api/campaigns/{camp['id']}").json()
    assert len(detail["companies"]) == 3
    assert {r["stage"] for r in detail["rejections"]} == {"qualifier", "quick_filter", "code_check"}


def test_home(client):
    approve_first(client)
    h = client.get("/api/home").json()
    assert h["stats"]["emailed"] == 1
    assert len(h["waiting"]) == 2  # two drafts still waiting
    assert h["pipeline"][0]["step"] == 3


def test_manual_suppression_by_domain_blocks(client):
    tid = approve_first(client)
    t = client.get(f"/api/threads/{tid}").json()
    domain = t["contact"]["email"].split("@")[1]
    client.post("/api/suppressions", json={"email": f"@{domain}"})
    res = client.post(f"/api/threads/{tid}/send", json={"body": "Hi there."})
    assert res.status_code == 409


def test_email_service_refusal_is_a_clear_409_not_a_crash(client, monkeypatch):
    from app.services import outbox

    monkeypatch.setattr(settings, "resend_api_key", "re_test")

    def refuse(payload):
        raise RuntimeError("Invalid `to` field")

    monkeypatch.setattr(outbox.resend.Emails, "send", refuse)
    draft = client.get("/api/review").json()[0]
    res = client.post(f"/api/review/{draft['id']}/approve", json={})
    assert res.status_code == 409 and "refused" in res.json()["detail"]
    assert client.get("/api/outbox").json() == []  # nothing stored as sent
    assert len(client.get("/api/review").json()) == 3  # the draft is still waiting


def fake_writer(monkeypatch, body):
    """The writer always returns `body`; counts how many times it was asked."""
    from app.agents.schemas import FirstEmail, Strategy

    asked = {"n": 0}

    def structured(system, user, schema, chain_names=None):
        if schema is FirstEmail:
            asked["n"] += 1
            ids = [int(x) for x in __import__("re").findall(r"id (\d+):", user)]
            return FirstEmail(
                strategy=Strategy(
                    voice="short_plain",
                    trigger_evidence_id=ids[0],
                    pain="Payouts.",
                    avoid=[],
                    follow_up_angles=[{"step": n, "angle": "a"} for n in (1, 2, 3)],
                ),
                subject="wholesale at fernhill",
                body=body,
                citations=[ids[0]],
                confidence="high",
            )
        if schema is FactCheckResult:
            return FactCheckResult(sentences=[SentenceCheck(sentence="x", supported=True)])
        raise llm.LLMNotConfigured("not in this test")

    monkeypatch.setattr(llm, "structured", structured)
    return asked


def test_redo_rewrites_the_draft(client, monkeypatch):
    good = (
        "Hi Ana, saw Fernhill Goods is hiring an operations manager [1]. Growing teams "
        "usually find the books fall behind first: payouts, inventory and wholesale invoices "
        "all need matching each month. Ledgerwise does monthly bookkeeping for e-commerce "
        "brands, so founders stop reconciling at night. Worth a short call to see if it fits?"
    )
    fake_writer(monkeypatch, good)
    draft = client.get("/api/review").json()[0]
    out = client.post(f"/api/review/{draft['id']}/redo").json()
    assert "operations manager" in out["body"]
    assert all(c["passed"] for c in out["checks"]) and out["handoff_reason"] == ""


def test_agent_fixes_checks_itself_then_asks_a_person_in_plain_words(client, monkeypatch):
    asked = fake_writer(monkeypatch, "Hi Ana, saw you hire [1]. Worth a call?")  # always too short
    draft = client.get("/api/review").json()[0]
    out = client.post(f"/api/review/{draft['id']}/redo").json()
    assert asked["n"] == 3  # the agent tried to fix it itself first
    assert out["handoff_reason"].startswith("I tried 3 times and this rule is still broken")
    assert "words" in out["handoff_reason"]


ORIGINAL = (
    "Hi Ana, I saw Fernhill now sells on Amazon as well as your own store. "
    "Running two channels often means two sets of payouts to match each month. "
    "Would a short call next week be useful?"
)


def test_rewrite_retries_when_ai_replaces_the_email(monkeypatch):
    from app.agents import writer
    from app.agents.schemas import Rewrite

    calls = []

    def structured(system, user, schema, chain_names=None):
        calls.append(user)
        if len(calls) == 1:  # first try: a brand new pitch, not an edit
            return Rewrite(
                body="Hello! Ledgerwise is the best bookkeeping firm. Book now.",
                what_changed="rewrote",
            )
        return Rewrite(
            body=ORIGINAL.replace("Hi Ana", "Hi Ana, hope your week is going well"),
            what_changed="warmer opener",
        )

    monkeypatch.setattr(llm, "structured", structured)
    out = writer.rewrite("context", ORIGINAL, "warmer")
    assert len(calls) == 2 and "CHANGED TOO MUCH" in calls[1]
    assert "Amazon" in out.body and writer.kept_share(ORIGINAL, out.body) > 0.7


def test_rewrite_allows_full_rewrite_when_asked(monkeypatch):
    from app.agents import writer
    from app.agents.schemas import Rewrite

    calls = []

    def structured(system, user, schema, chain_names=None):
        calls.append(user)
        return Rewrite(body="A totally different email.", what_changed="rewrote")

    monkeypatch.setattr(llm, "structured", structured)
    writer.rewrite("context", ORIGINAL, "rewrite it from scratch")
    assert len(calls) == 1


def test_rendered_email_is_branded_but_plain():
    text, html = render("Hi Ana,\n\nWorth a call?", 7)
    assert "#FFC600" in html and "Ledgerwise" in html and "Ledgerwise" in text
    assert "<img" not in html and "unsubscribe" in html


def test_rerun_starts_same_search_again(client, monkeypatch):
    started = []
    monkeypatch.setattr(campaigns_api, "_run_in_background", lambda cid: started.append(cid))
    first = client.post("/api/campaigns", json={"name": "Candles", "categories": ["Candles"]})
    cid = first.json()["id"]
    assert client.post(f"/api/campaigns/{cid}/rerun").status_code == 409  # still running
    client.post(f"/api/campaigns/{cid}/stop")
    again = client.post(f"/api/campaigns/{cid}/rerun").json()
    assert again["id"] != cid and again["name"] == "Candles (2)"
    assert again["settings"]["categories"] == ["Candles"] and started[-1] == again["id"]


def test_test_mode_sends_to_my_inbox(client, monkeypatch):
    sent = []
    monkeypatch.setattr(outbox.settings, "resend_api_key", "re_test")
    monkeypatch.setattr(outbox.resend.Emails, "send", lambda p: sent.append(p) or {"id": "x"})
    assert client.get("/api/test-mode").json()["on"] is False
    assert client.put("/api/test-mode", json={"email": "not-an-email"}).status_code == 422
    on = client.put("/api/test-mode", json={"email": " Me@Example.org "}).json()
    assert on == {"on": True, "email": "me@example.org", "demo_inbox": "delivered@resend.dev"}
    approve_first(client)
    assert sent[-1]["to"] == ["me@example.org"]
    client.put("/api/test-mode", json={"email": ""})
    assert client.get("/api/test-mode").json()["on"] is False
