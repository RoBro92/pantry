from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from fractions import Fraction
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


_MIXED_FRACTION_RE = re.compile(r"^(?P<whole>\d+)\s+(?P<fraction>\d+/\d+)$")
_QUANTITY_WITH_SUFFIX_RE = re.compile(r"^(?P<number>\d+(?:\.\d+)?|\d+/\d+|\d+\s+\d+/\d+)\s*(?P<suffix>.+)?$")
_NON_NUMERIC_QUANTITY_NOTES = {
    "to taste",
    "as needed",
    "for serving",
    "to serve",
    "optional",
}


def _parse_provider_quantity_number(value: str) -> Decimal | None:
    text = value.strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except Exception:
        pass

    mixed_match = _MIXED_FRACTION_RE.match(text)
    if mixed_match is not None:
        return Decimal(mixed_match.group("whole")) + Decimal(str(float(Fraction(mixed_match.group("fraction")))))

    if "/" in text:
        try:
            return Decimal(str(float(Fraction(text))))
        except Exception:
            return None
    return None


def _normalize_provider_quantity_fields(data: dict[str, Any]) -> dict[str, Any]:
    raw_quantity = data.get("quantity")
    raw_unit = str(data.get("unit") or "").strip()
    raw_note = str(data.get("note") or "").strip()

    if data.get("is_extra_ingredient") is None:
        data["is_extra_ingredient"] = False

    if isinstance(raw_quantity, str):
        normalized_quantity = _parse_provider_quantity_number(raw_quantity)
        if normalized_quantity is not None:
            data["quantity"] = normalized_quantity
            return data

        quantity_text = raw_quantity.strip()
        suffix_match = _QUANTITY_WITH_SUFFIX_RE.match(quantity_text)
        if suffix_match is not None:
            numeric = _parse_provider_quantity_number(suffix_match.group("number"))
            suffix = (suffix_match.group("suffix") or "").strip()
            if numeric is not None:
                data["quantity"] = numeric
                if suffix and not raw_unit:
                    data["unit"] = suffix
                return data

        if quantity_text.casefold() in _NON_NUMERIC_QUANTITY_NOTES:
            data["quantity"] = Decimal("0.000")
            data["unit"] = raw_unit or "portion"
            data["note"] = raw_note or quantity_text

    return data


class AIProviderConfigUpsertRequest(BaseModel):
    provider_type: Literal["openai", "openrouter", "litellm", "claude", "gemini", "ollama"]
    base_url: str
    default_model: str
    api_key: str | None = None
    is_enabled: bool = True


class AIProviderConfigSummary(BaseModel):
    external_id: str
    scope_type: str
    provider_type: str
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


class AIHouseholdMemberSummary(BaseModel):
    user_external_id: str
    display_name: str
    dietary_preferences: list[str] = Field(default_factory=list)


class AIMealPlannerPantrySummary(BaseModel):
    pantry_product_count: int
    active_lot_count: int
    near_expiry_lot_count: int
    near_expiry_product_names: list[str] = Field(default_factory=list)
    local_recipe_count: int


class AIMealPlannerResponse(BaseModel):
    household_external_id: str
    household_name: str
    feature: AIFeatureStatusSummary
    household_dietary_preferences: list[str] = Field(default_factory=list)
    members: list[AIHouseholdMemberSummary] = Field(default_factory=list)
    pantry_summary: AIMealPlannerPantrySummary


class AIMealSuggestionRequest(BaseModel):
    people_count: int = Field(ge=1, le=12)
    selected_user_external_ids: list[str] = Field(default_factory=list)
    meal_type: Literal["breakfast", "lunch", "dinner"]
    extra_portion_count: int = Field(default=0, ge=0, le=12)
    max_total_minutes: int | None = Field(default=None, ge=5, le=360)
    prioritize_near_expiry: bool = False
    allow_extra_ingredients: bool = True
    pantry_only: bool = False
    temporary_include_preferences: list[str] = Field(default_factory=list)
    temporary_exclude_preferences: list[str] = Field(default_factory=list)
    removed_preference_pills: list[str] = Field(default_factory=list)


class AIMealSuggestionContextSnapshot(BaseModel):
    pantry_product_count: int
    active_lot_count: int
    near_expiry_lot_count: int
    selected_user_count: int
    effective_preference_count: int
    candidate_recipe_count: int
    pantry_only: bool


class AIMealSuggestionSourceMetadata(BaseModel):
    kind: Literal["ai_generated", "household_recipe_reference", "external_recipe_reference"]
    label: str
    recipe_external_id: str | None = None
    recipe_title: str | None = None
    recipe_url: str | None = None
    provider_name: str | None = None


class AIMealSuggestionIngredient(BaseModel):
    id: str
    name: str
    quantity: Decimal
    unit: str
    note: str | None = None
    pantry_product_external_id: str | None = None
    pantry_product_name: str | None = None
    pantry_match_source: str | None = None
    availability_status: Literal["available", "partial", "missing", "unmatched", "unit_mismatch"]
    pantry_available_quantity: Decimal = Decimal("0.000")
    covered_quantity: Decimal = Decimal("0.000")
    missing_quantity: Decimal = Decimal("0.000")
    uses_near_expiry_item: bool = False
    is_extra_ingredient: bool = False
    can_consume_from_pantry: bool = False


class AIMealSuggestion(BaseModel):
    id: str
    title: str
    short_summary: str
    why_it_matches: str
    total_time_minutes: int | None = None
    pantry_ingredients_available: list[str] = Field(default_factory=list)
    extra_ingredients_needed: list[str] = Field(default_factory=list)
    dietary_fit_summary: str
    near_expiry_note: str | None = None
    source: AIMealSuggestionSourceMetadata
    ingredients: list[AIMealSuggestionIngredient] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)


class AIMealSuggestionResponse(BaseModel):
    household_external_id: str
    feature: AIFeatureStatusSummary
    request: AIMealSuggestionRequest
    context_snapshot: AIMealSuggestionContextSnapshot
    suggestions: list[AIMealSuggestion] = Field(default_factory=list)
    generated_at: datetime


class CompleteAIMealSuggestionIngredientRequest(BaseModel):
    ingredient_id: str
    name: str
    quantity: Decimal
    unit: str
    pantry_product_external_id: str | None = None
    consume_quantity: Decimal = Field(default=Decimal("0.000"), ge=0)


class CompleteAIMealSuggestionRequest(BaseModel):
    suggestion_id: str
    suggestion_title: str
    ingredients: list[CompleteAIMealSuggestionIngredientRequest] = Field(default_factory=list)


class CompletedAIMealSuggestionIngredient(BaseModel):
    ingredient_id: str
    name: str
    unit: str
    requested_quantity: Decimal
    consumed_quantity: Decimal
    pantry_product_external_id: str | None = None
    pantry_product_name: str | None = None
    status: Literal["consumed", "partially_consumed", "skipped", "missing"]
    note: str | None = None


class CompleteAIMealSuggestionResponse(BaseModel):
    completed: bool
    suggestion_id: str
    suggestion_title: str
    consumed_ingredients: list[CompletedAIMealSuggestionIngredient] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AIProviderMealSuggestionIngredient(BaseModel):
    name: str
    quantity: Decimal
    unit: str
    note: str | None = None
    pantry_product_external_id: str | None = None
    is_extra_ingredient: bool = False

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def normalize_quantity_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return _normalize_provider_quantity_fields(dict(data))
        return data


class AIProviderMealSuggestionSource(BaseModel):
    kind: Literal["ai_generated", "household_recipe_reference", "external_recipe_reference"]
    label: str
    recipe_external_id: str | None = None
    recipe_title: str | None = None
    recipe_url: str | None = None
    provider_name: str | None = None

    model_config = ConfigDict(extra="forbid")


class AIProviderMealSuggestionItem(BaseModel):
    title: str
    short_summary: str
    why_it_matches: str
    total_time_minutes: int | None = Field(default=None, ge=1, le=360)
    dietary_fit_summary: str
    source: AIProviderMealSuggestionSource
    ingredients: list[AIProviderMealSuggestionIngredient] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list, min_length=1, max_length=10)

    model_config = ConfigDict(extra="forbid")


class AIProviderMealSuggestionOutput(BaseModel):
    suggestions: list[AIProviderMealSuggestionItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
