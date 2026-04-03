from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.setup import SetupStatusResponse
from app.services.audit import record_audit_event
from app.services.auth import count_platform_admins, create_platform_admin, get_user_by_external_id


def get_setup_status(db: Session) -> SetupStatusResponse:
    platform_admin_count = count_platform_admins(db)
    is_initialized = platform_admin_count > 0
    return SetupStatusResponse(
        is_initialized=is_initialized,
        platform_admin_count=platform_admin_count,
        can_bootstrap_platform_admin=not is_initialized,
        recommended_next_step=(
            "Create the first platform admin."
            if not is_initialized
            else "Sign in and continue in the app."
        ),
    )


def bootstrap_first_platform_admin(
    db: Session,
    *,
    email: str,
    password: str,
    display_name: str | None,
) -> User:
    if count_platform_admins(db) > 0:
        raise ValueError("Initial setup has already been completed.")

    user = create_platform_admin(
        db,
        email=email,
        password=password,
        display_name=display_name,
    )
    record_audit_event(
        db,
        household=None,
        actor=user,
        action="setup.platform_admin_bootstrapped",
        target_type="user",
        target_external_id=user.external_id,
        event_metadata={
            "email": user.email,
            "display_name": user.display_name,
        },
    )
    db.commit()
    return get_user_by_external_id(db, user.external_id) or user
