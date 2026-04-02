from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from fastapi import APIRouter, Depends

from app.api.deps.auth import require_platform_admin
from app.core.db import get_db_session
from app.models.household import Household
from app.models.membership import Membership
from app.models.role import Role
from app.models.user import User
from app.schemas.admin import AdminHouseholdSummary, AdminOverviewResponse, AdminUserSummary

router = APIRouter(prefix="/platform-admin", tags=["platform-admin"])


@router.get("/overview", response_model=AdminOverviewResponse)
def get_overview(_: User = Depends(require_platform_admin), db: Session = Depends(get_db_session)):
    platform_admin_count = db.scalar(
        select(func.count(User.id))
        .join(Role, User.platform_role_id == Role.id)
        .where(Role.code == "platform_admin")
    )
    return AdminOverviewResponse(
        user_count=db.scalar(select(func.count(User.id))) or 0,
        platform_admin_count=platform_admin_count or 0,
        household_count=db.scalar(select(func.count(Household.id))) or 0,
        membership_count=db.scalar(select(func.count(Membership.id))) or 0,
    )


@router.get("/users", response_model=list[AdminUserSummary])
def list_users(_: User = Depends(require_platform_admin), db: Session = Depends(get_db_session)):
    membership_counts = {
        user_id: count
        for user_id, count in db.execute(
            select(Membership.user_id, func.count(Membership.id)).group_by(Membership.user_id)
        ).all()
    }

    users = db.scalars(select(User).options(selectinload(User.platform_role)).order_by(User.email)).all()
    return [
        AdminUserSummary(
            external_id=user.external_id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            platform_role=user.platform_role.code if user.platform_role else None,
            membership_count=membership_counts.get(user.id, 0),
        )
        for user in users
    ]


@router.get("/households", response_model=list[AdminHouseholdSummary])
def list_households(_: User = Depends(require_platform_admin), db: Session = Depends(get_db_session)):
    membership_counts = {
        household_id: count
        for household_id, count in db.execute(
            select(Membership.household_id, func.count(Membership.id)).group_by(Membership.household_id)
        ).all()
    }

    households = db.scalars(select(Household).order_by(Household.name)).all()
    return [
        AdminHouseholdSummary(
            external_id=household.external_id,
            name=household.name,
            membership_count=membership_counts.get(household.id, 0),
        )
        for household in households
    ]
