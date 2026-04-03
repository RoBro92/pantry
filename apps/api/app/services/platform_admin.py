from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.roles import HOUSEHOLD_ROLE_CODES
from app.models.household import Household
from app.models.membership import Membership
from app.models.user import User
from app.services.audit import record_audit_event
from app.services.auth import create_household, create_user, get_user_by_external_id
from app.services.roles import get_role_by_code


def create_managed_user(
    db: Session,
    *,
    actor: User,
    email: str,
    password: str,
    display_name: str | None,
) -> User:
    user = create_user(
        db,
        email=email,
        password=password,
        display_name=display_name,
    )
    record_audit_event(
        db,
        household=None,
        actor=actor,
        action="admin.user.created",
        target_type="user",
        target_external_id=user.external_id,
        event_metadata={
            "email": user.email,
            "display_name": user.display_name,
        },
    )
    db.commit()
    return get_user_by_external_id(db, user.external_id) or user


def create_managed_household(
    db: Session,
    *,
    actor: User,
    name: str,
) -> Household:
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Household name is required.")

    existing = db.scalar(
        select(Household).where(func.lower(Household.name) == normalized_name.casefold())
    )
    if existing is not None:
        raise ValueError("A household with that name already exists.")

    household = create_household(db, name=normalized_name)
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="admin.household.created",
        target_type="household",
        target_external_id=household.external_id,
        event_metadata={"name": household.name},
    )
    db.commit()
    db.refresh(household)
    return household


def upsert_household_membership(
    db: Session,
    *,
    actor: User,
    household_external_id: str,
    user_external_id: str,
    role_code: str,
) -> Membership:
    household = db.scalar(select(Household).where(Household.external_id == household_external_id))
    if household is None:
        raise ValueError("Household not found.")

    user = get_user_by_external_id(db, user_external_id)
    if user is None:
        raise ValueError("User not found.")

    if role_code not in HOUSEHOLD_ROLE_CODES:
        raise ValueError("Household role must be household_admin or household_user.")

    role = get_role_by_code(db, role_code)
    if role is None:
        raise ValueError(f"Required role {role_code} is missing.")

    membership = db.scalar(
        select(Membership)
        .where(Membership.household_id == household.id)
        .where(Membership.user_id == user.id)
    )
    created = membership is None
    if membership is None:
        membership = Membership(
            household_id=household.id,
            user_id=user.id,
            role_id=role.id,
            is_active=True,
        )
    else:
        membership.role_id = role.id
        membership.is_active = True

    db.add(membership)
    db.flush()
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="admin.membership.created" if created else "admin.membership.updated",
        target_type="membership",
        target_external_id=membership.external_id,
        event_metadata={
            "household_external_id": household.external_id,
            "user_external_id": user.external_id,
            "role": role.code,
            "is_active": membership.is_active,
        },
    )
    db.commit()
    db.refresh(membership)
    return membership
