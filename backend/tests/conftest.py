import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import seed
from app.agents import llm
from app.config import settings
from app.db import Base, get_db
from app.main import app


@pytest.fixture(autouse=True)
def offline_llm(monkeypatch):
    """Tests never reach a real LLM, and start with no rotation history or cooldowns."""
    for pool in ("providers", "fast", "read", "judge", "write", "check"):
        monkeypatch.setattr(settings, f"llm_{pool}", "")
    monkeypatch.setattr(settings, "quick_filter_providers", "")
    llm.reset_rotation()


@pytest.fixture
def client(monkeypatch):
    """API client on a fresh in-memory database with the sample data, logged in."""
    monkeypatch.setattr(settings, "llm_providers", "")  # tests never call a real LLM
    monkeypatch.setattr(settings, "resend_api_key", "")  # ...or send real email
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(seed, "SessionLocal", TestSession)
    seed.run()

    def override():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    c = TestClient(app)
    res = c.post(
        "/api/auth/login", json={"email": "sales@ledgerwise.test", "password": "ledgerwise-demo"}
    )
    assert res.status_code == 200
    yield c
    app.dependency_overrides.clear()
