from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password, normalize_email, password_needs_rehash, verify_password
from app.domain.roles import PLATFORM_ADMIN_ROLE
from app.models.membership import Membership
from app.models.user import User
from app.schemas.auth import SessionMembership, SessionResponse, SessionUser
from app.services.roles import get_role_by_code


def get_user_by_email(db: Session, email: str) -> User | None:
    normalized_email = normalize_email(email)
    return db.scalar(
        select(User)
        .where(User.email == normalized_email)
        .options(
            selectinload(User.platform_role),
            selectinload(User.memberships).selectinload(Membership.household),
            selectinload(User.memberships).selectinload(Membership.role),
        )
    )


def get_user_by_external_id(db: Session, external_id: str) -> User | None:
    return db.scalar(
        select(User)
        .where(User.external_id == external_id)
        .options(
            selectinload(User.platform_role),
            selectinload(User.memberships).selectinload(Membership.household),
            selectinload(User.memberships).selectinload(Membership.role),
        )
    )


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)

    if user is None or not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return get_user_by_external_id(db, user.external_id)


def build_session_response(user: User) -> SessionResponse:
    memberships = sorted(
        [
            SessionMembership(
                external_id=membership.external_id,
                household_external_id=membership.household.external_id,
                household_name=membership.household.name,
                role=membership.role.code,
                is_active=membership.is_active,
            )
            for membership in user.memberships
            if membership.is_active
        ],
        key=lambda item: item.household_name.lower(),
    )

    return SessionResponse(
        authenticated=True,
        user=SessionUser(
            external_id=user.external_id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            platform_role=user.platform_role.code if user.platform_role else None,
        ),
        memberships=memberships,
    )


def create_platform_admin(
    db: Session,
    *,
    email: str,
    password: str,
    display_name: str | None,
) -> User:
    if get_user_by_email(db, email) is not None:
        raise ValueError("A user with that email already exists.")

    role = get_role_by_code(db, PLATFORM_ADMIN_ROLE)
    if role is None:
        raise ValueError("Required role platform_admin is missing.")

    user = User(
        email=normalize_email(email),
        password_hash=hash_password(password),
        display_name=display_name.strip() if display_name else None,
        platform_role_id=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return get_user_by_external_id(db, user.external_id)


def count_platform_admins(db: Session) -> int:
    role = get_role_by_code(db, PLATFORM_ADMIN_ROLE)
    if role is None:
        return 0

    return db.query(User).filter(User.platform_role_id == role.id).count()


def reset_user_password(db: Session, *, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if user is None:
        raise ValueError("No user exists with that email.")

    user.password_hash = hash_password(password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

