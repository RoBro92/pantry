from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.roles import HOUSEHOLD_ADMIN_ROLE, PLATFORM_ADMIN_ROLE
from app.models.household import Household
from app.models.membership import Membership
from app.models.user import User


@dataclass(frozen=True)
class HouseholdAccess:
    household: Household
    membership: Membership | None
    effective_role: str
    can_administer: bool


def resolve_household_access(
    db: Session,
    *,
    household_external_id: str,
    user: User,
    allowed_roles: set[str] | None = None,
) -> HouseholdAccess | None:
    household = db.scalar(select(Household).where(Household.external_id == household_external_id))
    if household is None:
        return None

    if user.platform_role and user.platform_role.code == PLATFORM_ADMIN_ROLE:
        return HouseholdAccess(
            household=household,
            membership=None,
            effective_role=PLATFORM_ADMIN_ROLE,
            can_administer=True,
        )

    membership = db.scalar(
        select(Membership)
        .where(Membership.user_id == user.id)
        .where(Membership.household_id == household.id)
        .where(Membership.is_active.is_(True))
    )

    if membership is None or membership.role is None:
        return None

    if allowed_roles and membership.role.code not in allowed_roles:
        return None

    return HouseholdAccess(
        household=household,
        membership=membership,
        effective_role=membership.role.code,
        can_administer=membership.role.code == HOUSEHOLD_ADMIN_ROLE,
    )

