from sqlalchemy.orm import Session

from app.models import AuditEvent


def log(db: Session, actor: str, action: str, entity_type: str, entity_id: int, **detail) -> None:
    """Add an audit row. The caller commits together with the action itself."""
    db.add(
        AuditEvent(
            actor=actor, action=action, entity_type=entity_type, entity_id=entity_id, detail=detail
        )
    )
