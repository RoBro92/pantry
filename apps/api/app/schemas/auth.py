from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class LoginRequest(BaseModel):
    identifier: str | None = None
    email: str | None = None
    password: str

    @model_validator(mode="after")
    def validate_identifier(self) -> "LoginRequest":
        if not (self.identifier or self.email):
            raise ValueError("A username or email is required.")
        return self


class SessionUser(BaseModel):
    external_id: str
    email: str
    display_name: str | None
    is_active: bool
    platform_role: str | None


class SessionMembership(BaseModel):
    external_id: str
    household_external_id: str
    household_name: str
    role: str
    is_active: bool


class SessionResponse(BaseModel):
    authenticated: bool
    user: SessionUser
    memberships: list[SessionMembership]

    model_config = ConfigDict(from_attributes=True)


class LogoutResponse(BaseModel):
    ok: bool
