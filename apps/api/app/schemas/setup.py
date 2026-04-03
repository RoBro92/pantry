from __future__ import annotations

from pydantic import BaseModel


class SetupStatusResponse(BaseModel):
    is_initialized: bool
    platform_admin_count: int
    can_bootstrap_platform_admin: bool
    recommended_next_step: str


class BootstrapPlatformAdminRequest(BaseModel):
    email: str
    display_name: str | None = None
    password: str
