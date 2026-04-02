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


class SMTPConfigResponse(BaseModel):
    effective: SMTPConfigValue
    effective_source: str
    stored: SMTPConfigValue
    configured: bool
    last_test_status: str
    last_tested_at: datetime | None
    last_test_error: str | None


class SMTPConfigUpdateRequest(BaseModel):
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    security: str | None = None
    is_enabled: bool = False


class SMTPTestResponse(BaseModel):
    ok: bool
    status: str
    message: str | None
    config: SMTPConfigResponse
