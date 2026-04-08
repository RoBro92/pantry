from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SMTPConfigValue(BaseModel):
    host: str | None
    port: int | None
    username: str | None
    has_password: bool
    from_email: str | None
    from_name: str | None
    security: str | None
    is_enabled: bool


class PasswordResetEmailTemplate(BaseModel):
    subject: str
    body_template: str


class PasswordResetEmailSettings(BaseModel):
    is_enabled: bool
    is_available: bool
    unavailable_reason: str | None = None
    template: PasswordResetEmailTemplate


class SMTPConfigResponse(BaseModel):
    effective: SMTPConfigValue
    effective_source: str
    stored: SMTPConfigValue
    configured: bool
    config_error: str | None = None
    last_test_status: str
    last_tested_at: datetime | None
    last_test_error: str | None
    password_reset: PasswordResetEmailSettings


class SMTPConfigUpdateRequest(BaseModel):
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    security: str | None = None
    is_enabled: bool = False
    password_reset_enabled: bool = False
    password_reset_subject_template: str | None = None
    password_reset_body_template: str | None = None


class SMTPTestResponse(BaseModel):
    ok: bool
    status: str
    message: str | None
    config: SMTPConfigResponse
