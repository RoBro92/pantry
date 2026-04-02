from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.household import Household
from app.models.user import User


def record_audit_event(
    db: Session,
    *,
    household: Household | None,
    actor: User | None,
    action: str,
    target_type: str,
    target_external_id: str,
    event_metadata: dict[str, object],
) -> AuditEvent:
    event = AuditEvent(
        household_id=household.id if household else None,
        actor_user_id=actor.id if actor else None,
        action=action,
        target_type=target_type,
        target_external_id=target_external_id,
        event_metadata=event_metadata,
    )
    db.add(event)
    return event
