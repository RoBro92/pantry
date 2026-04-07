from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


BackupScope = Literal["instance", "household"]


class BackupBundleSummary(BaseModel):
    format: str
    format_version: int
    scope: BackupScope
    app_version: str
    schema_revision: str | None = None
    exported_at: datetime
    household_external_id: str | None = None
    household_name: str | None = None
    table_counts: dict[str, int] = Field(default_factory=dict)


class StagedBackupResponse(BaseModel):
    stage_id: str
    original_filename: str
    size_bytes: int
    uploaded_at: datetime
    quarantine_path: str
    supported_for_restore: bool
    warnings: list[str] = Field(default_factory=list)
    bundle: BackupBundleSummary


class BackupRestoreRequest(BaseModel):
    stage_id: str
    confirmation_phrase: str


class BackupRestoreResponse(BaseModel):
    restored: bool
    requires_reauthentication: bool
    message: str
    bundle: BackupBundleSummary
