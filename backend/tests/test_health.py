from fastapi.testclient import TestClient

from app.main import app


def test_health():
    res = TestClient(app).get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_health_under_api_for_the_frontend():
    res = TestClient(app).get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
