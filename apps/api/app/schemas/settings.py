from __future__ import annotations

from pydantic import BaseModel


class PublicBaseURLSummary(BaseModel):
    stored_value: str | None
    effective_value: str
    effective_source: str


class PublicBaseURLUpdateRequest(BaseModel):
    public_base_url: str
