from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

SetupStepKey = Literal[
    "welcome",
    "users",
    "dietary",
    "household",
    "public_url",
    "ai",
    "smtp",
    "review",
]


class SetupStepState(BaseModel):
    key: SetupStepKey
    title: str
    required: bool
    is_complete: bool


class SetupStatusResponse(BaseModel):
    is_initialized: bool
    platform_admin_count: int
    can_bootstrap_platform_admin: bool
    recommended_next_step: str
    stage: Literal["not_started", "in_progress", "completed"]
    has_staged_progress: bool
    completed_at: datetime | None = None
    steps: list[SetupStepState] = Field(default_factory=list)


class StagedSetupUserSummary(BaseModel):
    stage_id: str
    login: str
    display_name: str | None = None
    password_saved: bool
    is_platform_admin: bool = False


class StagedSetupAssignmentSummary(BaseModel):
    stage_user_id: str
    role: Literal["household_admin", "household_user"]


class StagedSetupDietaryUserSummary(BaseModel):
    stage_user_id: str
    preferences: list[str] = Field(default_factory=list)


class StagedSetupAIConfigSummary(BaseModel):
    provider_type: Literal["ollama", "openai_compatible"] | None = None
    base_url: str | None = None
    default_model: str | None = None
    is_enabled: bool = False
    has_api_key: bool = False


class StagedSetupSMTPConfigSummary(BaseModel):
    host: str | None = None
    port: int | None = None
    username: str | None = None
    has_password: bool = False
    from_email: str | None = None
    from_name: str | None = None
    security: str | None = None
    is_enabled: bool = False


class SetupWizardStateResponse(BaseModel):
    status: SetupStatusResponse
    installation_mode: Literal["fresh_install", "restore_backup"] = "fresh_install"
    welcome_acknowledged: bool
    staged_restore: "SetupStagedRestoreSummary | None" = None
    admin_user: StagedSetupUserSummary
    initial_users: list[StagedSetupUserSummary] = Field(default_factory=list)
    household_name: str | None = None
    location_group_name: str | None = None
    storage_locations: list[str] = Field(default_factory=list)
    household_assignments: list[StagedSetupAssignmentSummary] = Field(default_factory=list)
    public_base_url: str | None = None
    skipped_optional_steps: list[SetupStepKey] = Field(default_factory=list)
    household_dietary_preferences: list[str] = Field(default_factory=list)
    user_dietary_preferences: list[StagedSetupDietaryUserSummary] = Field(default_factory=list)
    ai_config: StagedSetupAIConfigSummary = Field(default_factory=StagedSetupAIConfigSummary)
    smtp_config: StagedSetupSMTPConfigSummary = Field(default_factory=StagedSetupSMTPConfigSummary)
    can_complete: bool
    missing_requirements: list[str] = Field(default_factory=list)


class SetupWizardUserInput(BaseModel):
    stage_id: str
    login: str
    display_name: str | None = None
    password: str | None = None


class SetupWelcomeUpdateRequest(BaseModel):
    acknowledged: bool = True


class SetupModeUpdateRequest(BaseModel):
    installation_mode: Literal["fresh_install", "restore_backup"]


class SetupUsersUpdateRequest(BaseModel):
    admin_login: str
    admin_display_name: str | None = None
    admin_password: str | None = None
    initial_users: list[SetupWizardUserInput] = Field(default_factory=list)


class SetupHouseholdAssignmentInput(BaseModel):
    stage_user_id: str
    role: Literal["household_admin", "household_user"] = "household_user"


class SetupHouseholdUpdateRequest(BaseModel):
    household_name: str
    location_group_name: str | None = None
    storage_locations: list[str] = Field(default_factory=list)
    household_assignments: list[SetupHouseholdAssignmentInput] = Field(default_factory=list)


class SetupPublicURLUpdateRequest(BaseModel):
    public_base_url: str
    mark_skipped: bool = False


class SetupDietaryUserInput(BaseModel):
    stage_user_id: str
    preferences: list[str] = Field(default_factory=list)


class SetupDietaryUpdateRequest(BaseModel):
    household_preferences: list[str] = Field(default_factory=list)
    user_preferences: list[SetupDietaryUserInput] = Field(default_factory=list)
    mark_skipped: bool = False


class SetupAIConfigUpdateRequest(BaseModel):
    provider_type: Literal["ollama", "openai_compatible"] | None = None
    base_url: str | None = None
    default_model: str | None = None
    api_key: str | None = None
    is_enabled: bool = False
    mark_skipped: bool = False


class SetupSMTPConfigUpdateRequest(BaseModel):
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    security: str | None = None
    is_enabled: bool = False
    mark_skipped: bool = False


class LoginCompatibilityRequest(BaseModel):
    identifier: str | None = None
    email: str | None = None
    password: str

    @model_validator(mode="after")
    def validate_identifier(self) -> "LoginCompatibilityRequest":
        if not (self.identifier or self.email):
            raise ValueError("A username or email is required.")
        return self


class SetupStagedRestoreBundleSummary(BaseModel):
    format: str
    format_version: int
    scope: Literal["instance", "household"]
    app_version: str
    schema_revision: str | None = None
    exported_at: datetime
    household_external_id: str | None = None
    household_name: str | None = None
    table_counts: dict[str, int] = Field(default_factory=dict)


class SetupStagedRestoreSummary(BaseModel):
    stage_id: str
    original_filename: str
    size_bytes: int
    uploaded_at: datetime
    quarantine_path: str
    supported_for_restore: bool
    warnings: list[str] = Field(default_factory=list)
    bundle: SetupStagedRestoreBundleSummary
