from __future__ import annotations

from pydantic import BaseModel


class AdminOverviewResponse(BaseModel):
    user_count: int
    platform_admin_count: int
    household_count: int
    membership_count: int


class AdminUserSummary(BaseModel):
    external_id: str
    email: str
    display_name: str | None
    is_active: bool
    platform_role: str | None
    membership_count: int


class AdminHouseholdSummary(BaseModel):
    external_id: str
    name: str
    membership_count: int

