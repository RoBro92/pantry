from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.security import normalize_email
from app.domain.roles import PLATFORM_ADMIN_ROLE
from app.models.base import Base
from app.domain.roles import HOUSEHOLD_ROLE_CODES
from app.models.household import Household
from app.models.membership import Membership
from app.models.user import User
from app.services.audit import record_audit_event
from app.services.auth import create_household, create_user, get_user_by_email, get_user_by_external_id
from app.services.password_resets import request_password_reset, user_has_self_service_reset_email
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


def _count_platform_admins(db: Session) -> int:
    platform_role = get_role_by_code(db, PLATFORM_ADMIN_ROLE)
    if platform_role is None:
        raise ValueError("Required role platform_admin is missing.")
    return db.scalar(select(func.count(User.id)).where(User.platform_role_id == platform_role.id)) or 0


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


def update_managed_user(
    db: Session,
    *,
    actor: User,
    user_external_id: str,
    email: str,
    display_name: str | None,
    platform_role_code: str | None,
    memberships: list[dict[str, str]],
) -> User:
    user = get_user_by_external_id(db, user_external_id)
    if user is None:
        raise ValueError("User not found.")

    normalized_email = normalize_email(email)
    existing_user = get_user_by_email(db, normalized_email)
    if existing_user is not None and existing_user.id != user.id:
        raise ValueError("A user with that username or email already exists.")

    if platform_role_code not in {None, PLATFORM_ADMIN_ROLE}:
        raise ValueError("Platform role must be platform_admin or empty.")

    platform_role = get_role_by_code(db, platform_role_code) if platform_role_code else None
    if platform_role_code and platform_role is None:
        raise ValueError(f"Required role {platform_role_code} is missing.")
    if (
        user.platform_role is not None
        and user.platform_role.code == PLATFORM_ADMIN_ROLE
        and platform_role is None
        and _count_platform_admins(db) <= 1
    ):
        raise ValueError("Pantry must keep at least one platform admin.")

    desired_memberships: dict[str, str] = {}
    for membership in memberships:
        household_external_id = membership["household_external_id"]
        role_code = membership["role"]
        if role_code not in HOUSEHOLD_ROLE_CODES:
            raise ValueError("Household role must be household_admin or household_user.")
        desired_memberships[household_external_id] = role_code

    households = {
        household.external_id: household
        for household in db.scalars(select(Household).where(Household.external_id.in_(desired_memberships.keys()))).all()
    }
    missing_households = set(desired_memberships.keys()) - set(households.keys())
    if missing_households:
        raise ValueError("One or more households could not be found.")

    existing_memberships = {
        membership.household.external_id: membership
        for membership in user.memberships
        if membership.household is not None and membership.role is not None
    }

    for household_external_id, membership in existing_memberships.items():
        desired_role_code = desired_memberships.get(household_external_id)
        if desired_role_code is None:
            if membership.role.code == "household_admin" and _count_household_admins(db, household_id=membership.household_id) <= 1:
                raise ValueError("Each household must keep at least one household admin.")
            db.delete(membership)
            continue

        if membership.role.code == desired_role_code and membership.is_active:
            continue

        role = get_role_by_code(db, desired_role_code)
        if role is None:
            raise ValueError(f"Required role {desired_role_code} is missing.")
        if (
            membership.role.code == "household_admin"
            and desired_role_code != "household_admin"
            and _count_household_admins(db, household_id=membership.household_id) <= 1
        ):
            raise ValueError("Each household must keep at least one household admin.")
        membership.role_id = role.id
        membership.role = role
        membership.is_active = True
        db.add(membership)

    for household_external_id, desired_role_code in desired_memberships.items():
        if household_external_id in existing_memberships:
            continue
        role = get_role_by_code(db, desired_role_code)
        household = households[household_external_id]
        if role is None:
            raise ValueError(f"Required role {desired_role_code} is missing.")
        db.add(
            Membership(
                household_id=household.id,
                user_id=user.id,
                role_id=role.id,
                is_active=True,
            )
        )

    user.email = normalized_email
    user.display_name = display_name.strip() if display_name and display_name.strip() else None
    user.platform_role_id = platform_role.id if platform_role is not None else None
    user.platform_role = platform_role
    db.add(user)
    db.flush()
    record_audit_event(
        db,
        household=None,
        actor=actor,
        action="admin.user.updated",
        target_type="user",
        target_external_id=user.external_id,
        event_metadata={
            "email": user.email,
            "display_name": user.display_name,
            "platform_role": platform_role.code if platform_role is not None else None,
            "membership_count": len(desired_memberships),
        },
    )
    db.commit()
    return get_user_by_external_id(db, user.external_id) or user


def send_managed_user_password_reset(
    db: Session,
    *,
    actor: User,
    user_external_id: str,
) -> User:
    user = get_user_by_external_id(db, user_external_id)
    if user is None:
        raise ValueError("User not found.")
    if not user.is_active:
        raise ValueError("Only active users can receive password reset emails.")
    if not user_has_self_service_reset_email(user):
        raise ValueError("This user does not have an email address that can receive reset mail.")

    if not request_password_reset(db, email=user.email):
        raise ValueError("Could not send a password reset email for this user.")

    record_audit_event(
        db,
        household=None,
        actor=actor,
        action="admin.user.password_reset_requested",
        target_type="user",
        target_external_id=user.external_id,
        event_metadata={"email": user.email},
    )
    db.commit()
    return get_user_by_external_id(db, user.external_id) or user


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
