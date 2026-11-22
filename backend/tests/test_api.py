from fastapi.testclient import TestClient

from app.main import app


def test_requires_login():
    assert TestClient(app).get("/api/companies").status_code == 401


def test_wrong_password(client):
    res = client.post("/api/auth/login", json={"email": "sales@ledgerwise.test", "password": "x"})
    assert res.status_code == 401


def test_companies_sorted_by_score(client):
    scores = [c["score"] for c in client.get("/api/companies").json()]
    assert scores == sorted(scores, reverse=True)


def test_review_queue_has_citations(client):
    drafts = client.get("/api/review").json()
    assert len(drafts) == 3
    assert all(d["citations"] for d in drafts)
    assert all(all(c["passed"] for c in d["checks"]) for d in drafts)


def test_approve_creates_thread_and_goes_to_demo_inbox(client):
    draft = client.get("/api/review").json()[0]
    res = client.post(f"/api/review/{draft['id']}/approve", json={})
    assert res.status_code == 200
    assert res.json()["sent_to"] == "delivered@resend.dev"
    thread = client.get(f"/api/threads/{res.json()['thread_id']}").json()
    assert thread["messages"][0]["direction"] == "outbound"
    assert len(client.get("/api/review").json()) == 2


def test_edit_with_price_is_blocked(client):
    draft = client.get("/api/review").json()[0]
    res = client.post(
        f"/api/review/{draft['id']}/approve",
        json={"body": "Hi, our plans start at $400/month [1] [2]."},
    )
    assert res.status_code == 422
    failed = [c["name"] for c in res.json()["detail"]["checks"] if not c["passed"]]
    assert "no_price" in failed


def test_unsubscribe_reply_suppresses_and_blocks_manual_send(client):
    draft = client.get("/api/review").json()[0]
    thread_id = client.post(f"/api/review/{draft['id']}/approve", json={}).json()["thread_id"]

    out = client.post(f"/api/threads/{thread_id}/simulate-reply", json={"body": "unsubscribe"})
    assert out.json()["action"] == "suppress"

    thread = client.get(f"/api/threads/{thread_id}").json()
    assert thread["status"] == "suppressed"
    assert len(client.get("/api/suppressions").json()) == 1

    blocked = client.post(f"/api/threads/{thread_id}/send", json={"body": "One more thing..."})
    assert blocked.status_code == 409
    assert client.post(f"/api/threads/{thread_id}/release").status_code == 409


def test_no_llm_key_hands_off_to_human(client):
    draft = client.get("/api/review").json()[0]
    thread_id = client.post(f"/api/review/{draft['id']}/approve", json={}).json()["thread_id"]
    out = client.post(f"/api/threads/{thread_id}/simulate-reply", json={"body": "Tell me more"})
    assert out.json()["action"] == "handoff"
    thread = client.get(f"/api/threads/{thread_id}").json()
    assert thread["mode"] == "human" and thread["status"] == "needs_human"


def test_human_owned_thread_is_not_answered_by_agent(client):
    draft = client.get("/api/review").json()[0]
    thread_id = client.post(f"/api/review/{draft['id']}/approve", json={}).json()["thread_id"]
    client.post(f"/api/threads/{thread_id}/takeover")
    out = client.post(f"/api/threads/{thread_id}/simulate-reply", json={"body": "Sure, Tuesday?"})
    assert out.json()["action"] == "none"


def test_every_action_is_audited(client):
    draft = client.get("/api/review").json()[0]
    client.post(f"/api/review/{draft['id']}/approve", json={})
    actions = [a["action"] for a in client.get("/api/audit").json()]
    assert "draft_approved" in actions
