from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AIProviderConfigUpsertRequest(BaseModel):
    provider_type: Literal["openai", "claude", "ollama", "custom"]
    base_url: str
    default_model: str
    api_key: str | None = None
    is_enabled: bool = True


class AIProviderConfigSummary(BaseModel):
    external_id: str
    scope_type: str
    provider_type: Literal["openai", "claude", "ollama", "custom"]
    base_url: str
    default_model: str
    is_enabled: bool
    has_api_key: bool
    health_status: str
    health_checked_at: datetime | None = None
    health_error: str | None = None
    available_model_count: int
    capabilities: dict[str, Any]
    last_success_at: datetime | None = None
    updated_at: datetime


class AIProviderConfigResponse(BaseModel):
    feature_enabled: bool
    config: AIProviderConfigSummary | None = None


class AIProviderHealthSummary(BaseModel):
    status: str
    is_healthy: bool
    message: str | None = None
    models: list[str] = Field(default_factory=list)
    capabilities: dict[str, Any] = Field(default_factory=dict)


class AIProviderHealthResponse(BaseModel):
    feature_enabled: bool
    config: AIProviderConfigSummary
    health: AIProviderHealthSummary


class AIFeatureStatusSummary(BaseModel):
    feature_enabled: bool
    available: bool
    reason: str | None = None
    provider_type: str | None = None
    default_model: str | None = None
    config_external_id: str | None = None
    health_status: str | None = None
    health_checked_at: datetime | None = None


class AISuggestionRequest(BaseModel):
    kind: Literal["meal_suggestions", "expiry_first", "buy_a_few_extra", "recipe_gap"]
    limit: int = Field(default=3, ge=1, le=5)
    recipe_external_id: str | None = None


class AISuggestionItem(BaseModel):
    title: str
    summary: str
    rationale: str
    pantry_product_names: list[str] = Field(default_factory=list)
    expiring_product_names: list[str] = Field(default_factory=list)
    missing_product_names: list[str] = Field(default_factory=list)
    extra_ingredient_names: list[str] = Field(default_factory=list)
    substitution_ideas: list[str] = Field(default_factory=list)
    caution: str | None = None


class AISuggestionContextSnapshot(BaseModel):
    pantry_product_count: int
    active_lot_count: int
    near_expiry_lot_count: int
    recipe_count: int
    recipe_external_id: str | None = None
    recipe_title: str | None = None


class AISuggestionResponse(BaseModel):
    household_external_id: str
    feature: AIFeatureStatusSummary
    request: AISuggestionRequest
    context_snapshot: AISuggestionContextSnapshot
    suggestions: list[AISuggestionItem]
    generated_at: datetime


class AIProviderSuggestionItem(BaseModel):
    title: str
    summary: str
    rationale: str
    pantry_product_names: list[str] = Field(default_factory=list)
    expiring_product_names: list[str] = Field(default_factory=list)
    missing_product_names: list[str] = Field(default_factory=list)
    extra_ingredient_names: list[str] = Field(default_factory=list)
    substitution_ideas: list[str] = Field(default_factory=list)
    caution: str | None = None

    model_config = ConfigDict(extra="forbid")


class AIProviderSuggestionOutput(BaseModel):
    suggestions: list[AIProviderSuggestionItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
