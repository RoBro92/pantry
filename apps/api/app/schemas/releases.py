from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReleaseCheckResponse(BaseModel):
    configured: bool
    source_type: str | None
    repository: str | None
    current_version: str
    latest_version: str | None
    release_tag: str | None
    release_name: str | None
    release_notes_url: str | None
    published_at: datetime | None
    checked_at: datetime
    status: str
    update_available: bool | None
    message: str | None = None
