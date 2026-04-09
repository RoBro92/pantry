from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.base import Base
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


def rename_managed_household(
    db: Session,
    *,
    actor: User,
    household_external_id: str,
    name: str,
) -> Household:
    household = db.scalar(select(Household).where(Household.external_id == household_external_id))
    if household is None:
        raise ValueError("Household not found.")

    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Household name is required.")

    existing = db.scalar(
        select(Household)
        .where(func.lower(Household.name) == normalized_name.casefold())
        .where(Household.id != household.id)
    )
    if existing is not None:
        raise ValueError("A household with that name already exists.")

    previous_name = household.name
    household.name = normalized_name
    db.add(household)
    db.flush()
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="admin.household.renamed",
        target_type="household",
        target_external_id=household.external_id,
        event_metadata={
            "previous_name": previous_name,
            "name": household.name,
        },
    )
    db.commit()
    db.refresh(household)
    return household


def _count_household_admins(db: Session, *, household_id) -> int:
    admin_role = get_role_by_code(db, "household_admin")
    if admin_role is None:
        raise ValueError("Required role household_admin is missing.")
    return db.scalar(
        select(func.count(Membership.id))
        .where(Membership.household_id == household_id)
        .where(Membership.role_id == admin_role.id)
        .where(Membership.is_active.is_(True))
    ) or 0


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
        if (
            membership.role_id != role.id
            and membership.is_active
            and membership.role is not None
            and membership.role.code == "household_admin"
            and role.code != "household_admin"
            and _count_household_admins(db, household_id=household.id) <= 1
        ):
            raise ValueError("Each household must keep at least one household admin.")
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


def remove_household_membership(
    db: Session,
    *,
    actor: User,
    household_external_id: str,
    membership_external_id: str,
) -> None:
    membership = db.scalar(
        select(Membership)
        .join(Household, Membership.household_id == Household.id)
        .where(Household.external_id == household_external_id)
        .where(Membership.external_id == membership_external_id)
    )
    if membership is None:
        raise ValueError("Membership not found.")

    household = db.scalar(select(Household).where(Household.id == membership.household_id))
    user = db.scalar(select(User).where(User.id == membership.user_id))
    role = get_role_by_code(db, "household_admin")
    if household is None or user is None or role is None:
        raise ValueError("Membership could not be resolved.")

    if membership.role_id == role.id and _count_household_admins(db, household_id=household.id) <= 1:
        raise ValueError("Each household must keep at least one household admin.")

    db.delete(membership)
    db.flush()
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="admin.membership.removed",
        target_type="membership",
        target_external_id=membership.external_id,
        event_metadata={
            "household_external_id": household.external_id,
            "user_external_id": user.external_id,
            "email": user.email,
        },
    )
    db.commit()


def delete_managed_household(
    db: Session,
    *,
    actor: User,
    household_external_id: str,
    confirm_household_name: str,
    acknowledge_last_household_deletion: bool,
) -> None:
    household = db.scalar(select(Household).where(Household.external_id == household_external_id))
    if household is None:
        raise ValueError("Household not found.")

    if household.name.strip() != confirm_household_name.strip():
        raise ValueError("Enter the exact household name to delete it.")

    household_count = db.scalar(select(func.count(Household.id))) or 0
    if household_count <= 1 and not acknowledge_last_household_deletion:
        raise ValueError("Deleting the last household requires explicit acknowledgement.")

    membership_count = db.scalar(
        select(func.count(Membership.id)).where(Membership.household_id == household.id)
    ) or 0

    try:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name == "households":
                db.execute(delete(table).where(table.c.id == household.id))
                continue
            if table.name == "memberships":
                db.execute(delete(table).where(table.c.household_id == household.id))
                continue
            if "household_id" in table.c:
                db.execute(delete(table).where(table.c.household_id == household.id))

        record_audit_event(
            db,
            household=None,
            actor=actor,
            action="admin.household.deleted",
            target_type="household",
            target_external_id=household_external_id,
            event_metadata={
                "name": household.name,
                "membership_count": membership_count,
                "was_last_household": household_count <= 1,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
