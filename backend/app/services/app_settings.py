"""Settings the team changes from the app. Today: test mode (send every email to one inbox)."""

from sqlalchemy.orm import Session

from app.models import AppSetting

TEST_EMAIL = "test_email"


def get(db: Session, key: str) -> str:
    row = db.get(AppSetting, key)
    return row.value if row else ""


def put(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key) or AppSetting(key=key)
    row.value = value
    db.add(row)


def test_email(db: Session) -> str:
    """The person's own inbox when test mode is on, else ''."""
    return get(db, TEST_EMAIL)
