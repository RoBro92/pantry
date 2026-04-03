from __future__ import annotations

from pydantic import BaseModel, Field


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


class AdminHouseholdMemberSummary(BaseModel):
    membership_external_id: str
    user_external_id: str
    email: str
    display_name: str | None
    role: str
    is_active: bool


class AdminHouseholdSummary(BaseModel):
    external_id: str
    name: str
    membership_count: int
    memberships: list[AdminHouseholdMemberSummary] = Field(default_factory=list)


class CreateAdminUserRequest(BaseModel):
    email: str
    display_name: str | None = None
    password: str


class CreateAdminHouseholdRequest(BaseModel):
    name: str


class CreateAdminMembershipRequest(BaseModel):
    user_external_id: str
    role: str
