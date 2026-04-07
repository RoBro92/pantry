from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ReleaseStatus = Literal[
    "not_configured",
    "release_metadata_missing",
    "unavailable",
    "comparison_unavailable",
    "update_available",
    "ahead_of_latest_release",
    "up_to_date",
]

ReleaseMetadataStatus = Literal[
    "not_configured",
    "available",
    "release_missing",
    "request_failed",
]


class ReleaseNotesSummary(BaseModel):
    version: str
    release_tag: str
    release_name: str | None = None
    release_notes_url: str | None = None
    published_at: datetime | None = None
    changelog_summary: str | None = None
    breaking_change_notes: list[str] = Field(default_factory=list)
    manual_update_commands: list[str] = Field(default_factory=list)
    notes_source: Literal["release_json_asset", "github_release_body", "default_commands"] | None = None


class ReleaseCheckResponse(BaseModel):
    configured: bool
    source_type: str | None
    source_strategy: str
    repository: str | None
    metadata_status: ReleaseMetadataStatus
    current_version: str
    latest_version: str | None
    release_tag: str | None
    release_name: str | None
    release_notes_url: str | None
    published_at: datetime | None
    checked_at: datetime
    status: ReleaseStatus
    update_available: bool | None
    message: str | None = None
    latest_release: ReleaseNotesSummary | None = None
    current_release: ReleaseNotesSummary | None = None
    manual_update_commands: list[str] = Field(default_factory=list)
    notes_seen_version: str | None = None
    notes_seen_at: datetime | None = None
    show_whats_new_prompt: bool = False


class ReleaseNotesSeenResponse(BaseModel):
    release_status: ReleaseCheckResponse
