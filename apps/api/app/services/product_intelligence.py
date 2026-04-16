from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.ai import AI_HEALTH_UNHEALTHY
from app.models.base import utc_now
from app.models.household import Household
from app.models.product import Product
from app.models.product_intelligence import ProductIntelligence
from app.models.user import User
from app.schemas.pantry import (
    ProductIntelligenceStatusCounts,
    ProductIntelligenceStatusResponse,
    ProductIntelligenceStructuredMetadata,
    ProductIntelligenceSummary,
)
from app.services.ai_config import get_ai_feature_enabled, normalize_provider_model, resolve_provider_config
from app.services.ai_providers.openai_compat import is_supported_openai_model
from app.services.ai_providers import StructuredCompletionRequest
from app.services.ai_runtime import normalize_ai_error
from app.services.audit import record_audit_event
from app.services.pantry_normalization import lookup_tokens, normalize_text_tags, require_text
from app.services.product_enrichment import get_primary_enrichment
from app.services.product_intelligence_profiles import resolve_product_intelligence_profile

PRODUCT_INTELLIGENCE_SCOPE = "pantry_product_classification"
PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION = "v1"
PRODUCT_INTELLIGENCE_SCHEMA_VERSION = "2026-04-10"
PRODUCT_INTELLIGENCE_STALE_SCHEMA = "schema_changed"
PRODUCT_INTELLIGENCE_STALE_CLASSIFIER = "classification_version_changed"
PRODUCT_INTELLIGENCE_STALE_SOURCE = "source_product_data_changed"
PRODUCT_INTELLIGENCE_BASE_PROMPT_TOKEN_OVERHEAD = 650
PRODUCT_INTELLIGENCE_MAX_TRIM_LEVEL = 2
PRODUCT_INTELLIGENCE_SOURCE_PROVIDER_DERIVED = "pantry_derived"
PRODUCT_INTELLIGENCE_EXECUTION_FULL_AI = "full_ai"
PRODUCT_INTELLIGENCE_EXECUTION_AI_GAP_FILL = "ai_gap_fill"
PRODUCT_INTELLIGENCE_EXECUTION_DERIVED_ONLY = "derived_only"
PRODUCT_INTELLIGENCE_PATH_DERIVED_ONLY = PRODUCT_INTELLIGENCE_EXECUTION_DERIVED_ONLY
PRODUCT_INTELLIGENCE_PATH_AI_GAP_FILL = PRODUCT_INTELLIGENCE_EXECUTION_AI_GAP_FILL
PRODUCT_INTELLIGENCE_PATH_FULL_AI = PRODUCT_INTELLIGENCE_EXECUTION_FULL_AI
PRODUCT_INTELLIGENCE_RUN_PATHS = {
    PRODUCT_INTELLIGENCE_PATH_DERIVED_ONLY,
    PRODUCT_INTELLIGENCE_PATH_AI_GAP_FILL,
    PRODUCT_INTELLIGENCE_PATH_FULL_AI,
}

STRONG_OFF_MATCH_STATUSES = frozenset({"barcode_exact"})
SEMANTIC_GAP_FILL_KEYWORDS = frozenset(
    {
        "broth",
        "chutney",
        "curry",
        "dressing",
        "gravy",
        "ketchup",
        "marinade",
        "paste",
        "pesto",
        "puree",
        "pureed",
        "salsa",
        "sauce",
        "seasoning",
        "soup",
        "spread",
        "stock",
        "tomato",
        "tomatoes",
    }
)


@dataclass(frozen=True)
class DerivedStapleProfile:
    key: str
    match_tokens: frozenset[str]
    food_category: str
    primary_ingredient_type: str | None = None
    ingredient_family_overrides: tuple[str, ...] = ()
    recipe_role_tags: tuple[str, ...] = ()
    substitution_groups: tuple[str, ...] = ()
    pantry_use_tags: tuple[str, ...] = ("Pantry staple", "Shelf stable")
    product_format: str | None = None
    storage_profile: str | None = "Shelf stable"
    preparation_tags: tuple[str, ...] = ()


DERIVED_STAPLE_PROFILES: tuple[DerivedStapleProfile, ...] = (
    DerivedStapleProfile(
        key="pasta",
        match_tokens=frozenset(
            {
                "fusilli",
                "linguine",
                "macaroni",
                "noodle",
                "noodles",
                "pasta",
                "penne",
                "rigatoni",
                "spaghetti",
                "tagliatelle",
            }
        ),
        food_category="Dry pasta",
        primary_ingredient_type="Wheat",
        ingredient_family_overrides=("Wheat",),
        recipe_role_tags=("Carbohydrate", "Base"),
        substitution_groups=("Pasta",),
        pantry_use_tags=("Pantry staple", "Quick meal", "Shelf stable"),
        product_format="Dried",
        preparation_tags=("Boil",),
    ),
    DerivedStapleProfile(
        key="rice",
        match_tokens=frozenset({"arborio", "basmati", "jasmine", "rice"}),
        food_category="Rice",
        primary_ingredient_type="Rice",
        ingredient_family_overrides=("Rice",),
        recipe_role_tags=("Carbohydrate", "Base"),
        substitution_groups=("Rice",),
        pantry_use_tags=("Pantry staple", "Quick meal", "Shelf stable"),
        product_format="Dried",
        preparation_tags=("Boil",),
    ),
    DerivedStapleProfile(
        key="beans",
        match_tokens=frozenset(
            {
                "bean",
                "beans",
                "cannellini",
                "chickpea",
                "chickpeas",
                "haricot",
                "kidney",
                "lentil",
                "lentils",
                "legume",
                "legumes",
                "pulse",
                "pulses",
            }
        ),
        food_category="Legumes",
        primary_ingredient_type="Legumes",
        ingredient_family_overrides=("Legumes",),
        recipe_role_tags=("Protein", "Base"),
        substitution_groups=("Legumes",),
        pantry_use_tags=("Pantry staple", "Bulk cooking", "Shelf stable"),
        product_format="Canned",
    ),
    DerivedStapleProfile(
        key="flour",
        match_tokens=frozenset({"flour", "plain", "self", "raising", "strong", "wholemeal"}),
        food_category="Flour",
        primary_ingredient_type="Flour",
        ingredient_family_overrides=("Flour",),
        recipe_role_tags=("Baking",),
        substitution_groups=("Flour",),
        pantry_use_tags=("Pantry staple", "Baking", "Shelf stable"),
        product_format="Dried",
    ),
    DerivedStapleProfile(
        key="oats",
        match_tokens=frozenset({"muesli", "oat", "oats", "oatmeal", "porridge"}),
        food_category="Oats",
        primary_ingredient_type="Oats",
        ingredient_family_overrides=("Oats",),
        recipe_role_tags=("Carbohydrate", "Base"),
        substitution_groups=("Oats",),
        pantry_use_tags=("Pantry staple", "Breakfast", "Shelf stable"),
        product_format="Dried",
    ),
)


class ProductClassificationMetadataPayload(BaseModel):
    product_format: str | None = None
    storage_profile: str | None = None
    cuisine_tags: list[str] = Field(default_factory=list)
    flavour_tags: list[str] = Field(default_factory=list)
    preparation_tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("cuisine_tags", "flavour_tags", "preparation_tags", mode="before")
    @classmethod
    def _coerce_nullable_tag_lists(cls, value):
        return [] if value is None else value


class ProductClassificationOutput(BaseModel):
    confidence: float | None = Field(default=None, ge=0, le=1)
    rationale_short: str | None = None
    primary_ingredient_type: str | None = None
    ingredient_families: list[str] = Field(default_factory=list)
    food_category: str | None = None
    dietary_tags: list[str] = Field(default_factory=list)
    allergen_tags: list[str] = Field(default_factory=list)
    recipe_role_tags: list[str] = Field(default_factory=list)
    substitution_groups: list[str] = Field(default_factory=list)
    pantry_use_tags: list[str] = Field(default_factory=list)
    structured_metadata: ProductClassificationMetadataPayload = Field(
        default_factory=ProductClassificationMetadataPayload
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "ingredient_families",
        "dietary_tags",
        "allergen_tags",
        "recipe_role_tags",
        "substitution_groups",
        "pantry_use_tags",
        mode="before",
    )
    @classmethod
    def _coerce_nullable_lists(cls, value):
        return [] if value is None else value

    @field_validator("structured_metadata", mode="before")
    @classmethod
    def _coerce_nullable_metadata(cls, value):
        return {} if value is None else value


class ProductBatchClassificationOutput(ProductClassificationOutput):
    product_external_id: str

    model_config = ConfigDict(extra="forbid")


class ProductClassificationBatchOutput(BaseModel):
    items: list[ProductBatchClassificationOutput] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("items", mode="before")
    @classmethod
    def _coerce_nullable_items(cls, value):
        return [] if value is None else value


def build_product_classification_batch_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "product_external_id",
                        "confidence",
                        "rationale_short",
                        "primary_ingredient_type",
                        "ingredient_families",
                        "food_category",
                        "dietary_tags",
                        "allergen_tags",
                        "recipe_role_tags",
                        "substitution_groups",
                        "pantry_use_tags",
                        "structured_metadata",
                    ],
                    "properties": {
                        "product_external_id": {"type": "string"},
                        "confidence": {"type": ["number", "null"]},
                        "rationale_short": {"type": ["string", "null"]},
                        "primary_ingredient_type": {"type": ["string", "null"]},
                        "ingredient_families": {"type": "array", "items": {"type": "string"}},
                        "food_category": {"type": ["string", "null"]},
                        "dietary_tags": {"type": "array", "items": {"type": "string"}},
                        "allergen_tags": {"type": "array", "items": {"type": "string"}},
                        "recipe_role_tags": {"type": "array", "items": {"type": "string"}},
                        "substitution_groups": {"type": "array", "items": {"type": "string"}},
                        "pantry_use_tags": {"type": "array", "items": {"type": "string"}},
                        "structured_metadata": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "product_format",
                                "storage_profile",
                                "cuisine_tags",
                                "flavour_tags",
                                "preparation_tags",
                            ],
                            "properties": {
                                "product_format": {"type": ["string", "null"]},
                                "storage_profile": {"type": ["string", "null"]},
                                "cuisine_tags": {"type": "array", "items": {"type": "string"}},
                                "flavour_tags": {"type": "array", "items": {"type": "string"}},
                                "preparation_tags": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                },
            }
        },
    }


@dataclass(frozen=True)
class ProductIntelligenceStaleness:
    is_stale: bool
    reasons: list[str]


@dataclass(frozen=True)
class ProductIntelligenceExecutionPlan:
    strategy: str
    reason: str
    source_payload: dict[str, object]
    ai_payload: dict[str, object] | None = None
    derived_output: ProductClassificationOutput | None = None

    @property
    def path(self) -> str:
        return self.strategy

    @property
    def approx_input_tokens(self) -> int:
        if self.strategy == PRODUCT_INTELLIGENCE_EXECUTION_DERIVED_ONLY:
            return 0
        return estimate_product_intelligence_tokens(self.ai_payload or self.source_payload)


def get_primary_product_intelligence(product: Product) -> ProductIntelligence | None:
    return product.intelligence_records[0] if product.intelligence_records else None


def build_product_intelligence_status(
    db: Session,
    *,
    household: Household,
) -> ProductIntelligenceStatusResponse:
    products = _load_household_products(db, household=household)
    counts = _build_status_counts(products)
    latest_run = _build_latest_run_summary(db, household=household)

    if not get_ai_feature_enabled():
        return ProductIntelligenceStatusResponse(
            available=False,
            reason="AI features are disabled for this deployment.",
            counts=counts,
            classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
            classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
            schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
            latest_run=latest_run,
        )

    resolved = resolve_provider_config(db, household=household)
    if resolved is None:
        return ProductIntelligenceStatusResponse(
            available=False,
            reason="No AI provider is configured for this installation.",
            counts=counts,
            classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
            classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
            schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
            latest_run=latest_run,
        )

    record = resolved.record
    default_model = normalize_provider_model(record.provider_type, record.default_model)
    if not record.is_enabled:
        return ProductIntelligenceStatusResponse(
            available=False,
            reason="The configured AI provider is disabled.",
            provider_type=record.provider_type,
            default_model=default_model,
            health_status=record.health_status,
            counts=counts,
            classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
            classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
            schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
            latest_run=latest_run,
        )

    if record.health_status == AI_HEALTH_UNHEALTHY:
        if record.provider_type == "openai" and is_supported_openai_model(default_model):
            return ProductIntelligenceStatusResponse(
                available=True,
                provider_type=record.provider_type,
                default_model=default_model,
                health_status=record.health_status,
                counts=counts,
                classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
                classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
                schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
                latest_run=latest_run,
            )
        return ProductIntelligenceStatusResponse(
            available=False,
            reason=str(
                normalize_ai_error(
                    record.health_error or "The configured AI provider is unhealthy.",
                    provider_type=record.provider_type,
                    model=default_model,
                )
            ),
            provider_type=record.provider_type,
            default_model=default_model,
            health_status=record.health_status,
            counts=counts,
            classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
            classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
            schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
            latest_run=latest_run,
        )

    return ProductIntelligenceStatusResponse(
        available=True,
        provider_type=record.provider_type,
        default_model=default_model,
        health_status=record.health_status,
        counts=counts,
        classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
        classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
        schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
        latest_run=latest_run,
    )


def get_product_intelligence_staleness(
    product: Product,
    intelligence: ProductIntelligence | None,
) -> ProductIntelligenceStaleness:
    if intelligence is None:
        return ProductIntelligenceStaleness(is_stale=False, reasons=[])

    reasons: list[str] = []
    if intelligence.schema_version != PRODUCT_INTELLIGENCE_SCHEMA_VERSION:
        reasons.append(PRODUCT_INTELLIGENCE_STALE_SCHEMA)
    if intelligence.classification_version != PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION:
        reasons.append(PRODUCT_INTELLIGENCE_STALE_CLASSIFIER)
    if intelligence.source_data_hash != build_product_intelligence_source_data_hash(
        product,
        provider_type=intelligence.source_provider,
        model=intelligence.source_model,
    ):
        reasons.append(PRODUCT_INTELLIGENCE_STALE_SOURCE)
    return ProductIntelligenceStaleness(is_stale=bool(reasons), reasons=reasons)


def serialize_product_intelligence(
    intelligence: ProductIntelligence | None,
    *,
    product: Product | None = None,
) -> ProductIntelligenceSummary | None:
    if intelligence is None:
        return None

    staleness = (
        get_product_intelligence_staleness(product, intelligence)
        if product is not None
        else ProductIntelligenceStaleness(is_stale=False, reasons=[])
    )
    metadata = ProductIntelligenceStructuredMetadata.model_validate(intelligence.structured_metadata or {})
    return ProductIntelligenceSummary(
        source_provider=intelligence.source_provider,
        source_model=intelligence.source_model,
        classification_scope=intelligence.classification_scope,
        classification_version=intelligence.classification_version,
        schema_version=intelligence.schema_version,
        classified_at=intelligence.classified_at,
        confidence=intelligence.confidence,
        rationale_short=intelligence.rationale_short,
        primary_ingredient_type=intelligence.primary_ingredient_type,
        ingredient_families=list(intelligence.ingredient_families or []),
        food_category=intelligence.food_category,
        dietary_tags=list(intelligence.dietary_tags or []),
        allergen_tags=list(intelligence.allergen_tags or []),
        recipe_role_tags=list(intelligence.recipe_role_tags or []),
        substitution_groups=list(intelligence.substitution_groups or []),
        pantry_use_tags=list(intelligence.pantry_use_tags or []),
        structured_metadata=metadata,
        is_stale=staleness.is_stale,
        stale_reasons=staleness.reasons,
    )


def build_product_intelligence_source_data_hash(
    product: Product,
    *,
    provider_type: str | None = None,
    model: str | None = None,
) -> str:
    payload = build_product_intelligence_source_payload(
        product,
        provider_type=provider_type,
        model=model,
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_product_intelligence_source_payload(
    product: Product,
    *,
    provider_type: str | None = None,
    model: str | None = None,
) -> dict[str, object]:
    trim_level = get_product_intelligence_runtime_trim_level(
        product,
        provider_type=provider_type,
        model=model,
    )
    plan = build_product_intelligence_execution_plan(
        product,
        provider_type=provider_type,
        model=model,
        trim_level=trim_level,
        include_external_id=False,
    )
    return plan.source_payload


def build_product_intelligence_batch_source_payload(
    product: Product,
    *,
    trim_level: int = 0,
) -> dict[str, object]:
    plan = build_product_intelligence_execution_plan(
        product,
        trim_level=trim_level,
        include_external_id=True,
    )
    return plan.ai_payload or plan.source_payload


def build_product_intelligence_execution_plan(
    product: Product,
    *,
    provider_type: str | None = None,
    model: str | None = None,
    trim_level: int | None = None,
    include_external_id: bool = False,
) -> ProductIntelligenceExecutionPlan:
    if trim_level is None:
        trim_level = get_product_intelligence_runtime_trim_level(
            product,
            provider_type=provider_type,
            model=model,
        )

    enrichment = get_primary_enrichment(product)
    product_payload = _build_product_base_runtime_payload(
        product,
        trim_level=trim_level,
        enrichment_source_name=enrichment.source_product_name if enrichment is not None else None,
    )

    if enrichment is None:
        full_ai_payload = _build_full_ai_runtime_payload(
            product,
            enrichment=None,
            trim_level=trim_level,
            include_external_id=include_external_id,
            product_payload=product_payload,
        )
        return ProductIntelligenceExecutionPlan(
            strategy=PRODUCT_INTELLIGENCE_EXECUTION_FULL_AI,
            reason="manual_or_unenriched",
            source_payload=_wrap_execution_payload(
                full_ai_payload,
                strategy=PRODUCT_INTELLIGENCE_EXECUTION_FULL_AI,
                reason="manual_or_unenriched",
            ),
            ai_payload=_wrap_execution_payload(
                full_ai_payload,
                strategy=PRODUCT_INTELLIGENCE_EXECUTION_FULL_AI,
                reason="manual_or_unenriched",
            ),
        )

    derived_profile = _match_derived_staple_profile(product, enrichment=enrichment)
    derived_base = _build_off_derived_output(
        product,
        enrichment=enrichment,
        derived_profile=derived_profile,
        include_semantic_defaults=False,
    )
    full_ai_payload = _build_full_ai_runtime_payload(
        product,
        enrichment=enrichment,
        trim_level=trim_level,
        include_external_id=include_external_id,
        product_payload=product_payload,
    )

    if not _has_strong_off_signal(product, enrichment=enrichment, derived_base=derived_base):
        return ProductIntelligenceExecutionPlan(
            strategy=PRODUCT_INTELLIGENCE_EXECUTION_FULL_AI,
            reason="weak_off_signals",
            source_payload=_wrap_execution_payload(
                full_ai_payload,
                strategy=PRODUCT_INTELLIGENCE_EXECUTION_FULL_AI,
                reason="weak_off_signals",
            ),
            ai_payload=_wrap_execution_payload(
                full_ai_payload,
                strategy=PRODUCT_INTELLIGENCE_EXECUTION_FULL_AI,
                reason="weak_off_signals",
            ),
        )

    if derived_profile is not None and not _requires_semantic_gap_fill(product, enrichment=enrichment):
        derived_output = _build_off_derived_output(
            product,
            enrichment=enrichment,
            derived_profile=derived_profile,
            include_semantic_defaults=True,
        )
        derived_payload = _build_derived_only_payload(
            product_payload=product_payload,
            derived_output=derived_output,
            include_external_id=include_external_id,
            product_external_id=product.external_id,
        )
        return ProductIntelligenceExecutionPlan(
            strategy=PRODUCT_INTELLIGENCE_EXECUTION_DERIVED_ONLY,
            reason=f"derived_{derived_profile.key}",
            source_payload=_wrap_execution_payload(
                derived_payload,
                strategy=PRODUCT_INTELLIGENCE_EXECUTION_DERIVED_ONLY,
                reason=f"derived_{derived_profile.key}",
            ),
            derived_output=derived_output,
        )

    gap_fill_payload = _build_gap_fill_payload(
        product=product,
        enrichment=enrichment,
        product_payload=product_payload,
        derived_output=derived_base,
        include_external_id=include_external_id,
    )
    return ProductIntelligenceExecutionPlan(
        strategy=PRODUCT_INTELLIGENCE_EXECUTION_AI_GAP_FILL,
        reason="semantic_gap_fill",
        source_payload=_wrap_execution_payload(
            gap_fill_payload,
            strategy=PRODUCT_INTELLIGENCE_EXECUTION_AI_GAP_FILL,
            reason="semantic_gap_fill",
        ),
        ai_payload=_wrap_execution_payload(
            gap_fill_payload,
            strategy=PRODUCT_INTELLIGENCE_EXECUTION_AI_GAP_FILL,
            reason="semantic_gap_fill",
        ),
        derived_output=derived_base,
    )


def merge_product_intelligence_output(
    ai_output: ProductClassificationOutput,
    *,
    seed_output: ProductClassificationOutput | None,
) -> ProductClassificationOutput:
    if seed_output is None:
        return ai_output
    merged_metadata = ProductClassificationMetadataPayload(
        product_format=seed_output.structured_metadata.product_format or ai_output.structured_metadata.product_format,
        storage_profile=seed_output.structured_metadata.storage_profile or ai_output.structured_metadata.storage_profile,
        cuisine_tags=(
            list(seed_output.structured_metadata.cuisine_tags)
            if seed_output.structured_metadata.cuisine_tags
            else list(ai_output.structured_metadata.cuisine_tags)
        ),
        flavour_tags=(
            list(seed_output.structured_metadata.flavour_tags)
            if seed_output.structured_metadata.flavour_tags
            else list(ai_output.structured_metadata.flavour_tags)
        ),
        preparation_tags=(
            list(seed_output.structured_metadata.preparation_tags)
            if seed_output.structured_metadata.preparation_tags
            else list(ai_output.structured_metadata.preparation_tags)
        ),
    )
    return ProductClassificationOutput(
        confidence=seed_output.confidence if seed_output.confidence is not None else ai_output.confidence,
        rationale_short=seed_output.rationale_short or ai_output.rationale_short,
        primary_ingredient_type=seed_output.primary_ingredient_type or ai_output.primary_ingredient_type,
        ingredient_families=list(seed_output.ingredient_families or ai_output.ingredient_families),
        food_category=seed_output.food_category or ai_output.food_category,
        dietary_tags=list(seed_output.dietary_tags or ai_output.dietary_tags),
        allergen_tags=list(seed_output.allergen_tags or ai_output.allergen_tags),
        recipe_role_tags=list(seed_output.recipe_role_tags or ai_output.recipe_role_tags),
        substitution_groups=list(seed_output.substitution_groups or ai_output.substitution_groups),
        pantry_use_tags=list(seed_output.pantry_use_tags or ai_output.pantry_use_tags),
        structured_metadata=merged_metadata,
    )


def get_product_intelligence_runtime_trim_level(
    product: Product,
    *,
    provider_type: str | None = None,
    model: str | None = None,
) -> int:
    profile = resolve_product_intelligence_profile(provider_type or "", model)
    per_product_budget = max(
        (profile.max_input_tokens - PRODUCT_INTELLIGENCE_BASE_PROMPT_TOKEN_OVERHEAD)
        // max(profile.max_products_per_batch, 1),
        500,
    )
    for trim_level in range(PRODUCT_INTELLIGENCE_MAX_TRIM_LEVEL + 1):
        plan = build_product_intelligence_execution_plan(
            product,
            provider_type=provider_type,
            model=model,
            trim_level=trim_level,
            include_external_id=True,
        )
        payload = plan.ai_payload or plan.source_payload
        if estimate_product_intelligence_tokens(payload) <= per_product_budget:
            return trim_level
    return PRODUCT_INTELLIGENCE_MAX_TRIM_LEVEL


def _wrap_execution_payload(
    payload: dict[str, object],
    *,
    strategy: str,
    reason: str,
) -> dict[str, object]:
    return {
        "classification_strategy": strategy,
        "classification_reason": reason,
        **payload,
    }


def _build_product_base_runtime_payload(
    product: Product,
    *,
    trim_level: int,
    enrichment_source_name: str | None,
) -> dict[str, object]:
    alias_limit = 4 if trim_level == 0 else 2 if trim_level == 1 else 1
    notes_limit = 180 if trim_level == 0 else 120 if trim_level == 1 else 80
    manual_tag_limit = 10 if trim_level == 0 else 6 if trim_level == 1 else 4

    manual_tags = list(product.manual_ingredient_tags or [])[:manual_tag_limit]
    alias_names = _compact_runtime_text_list(
        [alias.name for alias in product.aliases],
        limit=alias_limit,
        exclude_names=[product.name, enrichment_source_name],
    )
    product_notes = _truncate_runtime_text(product.notes, notes_limit)

    product_payload: dict[str, object] = {
        "name": product.name,
        "default_unit": product.default_unit,
    }
    if alias_names:
        product_payload["aliases"] = alias_names
    if product_notes:
        product_payload["notes"] = product_notes
    if manual_tags:
        product_payload["manual_ingredient_tags"] = manual_tags
    return product_payload

def _build_full_ai_runtime_payload(
    product: Product,
    *,
    enrichment,
    trim_level: int,
    include_external_id: bool,
    product_payload: dict[str, object],
) -> dict[str, object]:
    payload: dict[str, object] = {"product": product_payload, "enrichment": None}
    if include_external_id:
        payload["product_external_id"] = product.external_id
    if enrichment is None:
        return payload

    ingredient_tags = _compact_runtime_text_list(
        list(enrichment.ingredient_tags or []),
        limit=14 if trim_level == 0 else 9 if trim_level == 1 else 5,
    )
    dietary_tags = _compact_runtime_text_list(
        list(enrichment.dietary_tags or []),
        limit=8 if trim_level == 0 else 6 if trim_level == 1 else 4,
    )
    allergen_tags = _compact_runtime_text_list(
        list(enrichment.allergen_tags or []),
        limit=8 if trim_level == 0 else 6 if trim_level == 1 else 4,
    )
    ingredient_signal_count = len(ingredient_tags) + len(list(product.manual_ingredient_tags or []))
    enrichment_payload: dict[str, object] = {}

    source_product_name = _truncate_runtime_text(
        enrichment.source_product_name,
        180 if trim_level == 0 else 120 if trim_level == 1 else 80,
    )
    alias_names = cast(list[str], list(product_payload.get("aliases", [])))
    if _is_meaningfully_different_name(source_product_name, product.name, alias_names):
        enrichment_payload["source_product_name"] = source_product_name
    if ingredient_tags:
        enrichment_payload["ingredient_tags"] = ingredient_tags
    if dietary_tags:
        enrichment_payload["dietary_tags"] = dietary_tags
    if allergen_tags:
        enrichment_payload["allergen_tags"] = allergen_tags

    category_hint = _select_category_hint(
        list(enrichment.categories or []),
        limit=60 if trim_level == 0 else 40 if trim_level == 1 else 28,
    )
    if category_hint:
        enrichment_payload["category_hint"] = category_hint

    ingredients_text = _truncate_runtime_text(
        enrichment.ingredients_text,
        240 if trim_level == 0 else 140 if trim_level == 1 else 90,
    )
    if ingredients_text and ingredient_signal_count < 2:
        enrichment_payload["ingredients_text"] = ingredients_text

    payload["enrichment"] = enrichment_payload or None
    return payload


def _build_derived_only_payload(
    *,
    product_payload: dict[str, object],
    derived_output: ProductClassificationOutput,
    include_external_id: bool,
    product_external_id: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "product": product_payload,
        "derived_facts": _serialize_derived_facts(derived_output),
    }
    if include_external_id:
        payload["product_external_id"] = product_external_id
    return payload


def _build_gap_fill_payload(
    *,
    product: Product,
    enrichment,
    product_payload: dict[str, object],
    derived_output: ProductClassificationOutput,
    include_external_id: bool,
) -> dict[str, object]:
    gap_signals: dict[str, object] = {}
    source_product_name = _truncate_runtime_text(enrichment.source_product_name, 120)
    alias_names = cast(list[str], list(product_payload.get("aliases", [])))
    if _is_meaningfully_different_name(source_product_name, product.name, alias_names):
        gap_signals["source_product_name"] = source_product_name

    category_hint = _select_category_hint(list(enrichment.categories or []), limit=48)
    if category_hint:
        gap_signals["category_hint"] = category_hint

    ingredient_tags = _compact_runtime_text_list(list(enrichment.ingredient_tags or []), limit=6)
    if ingredient_tags:
        gap_signals["ingredient_tags"] = ingredient_tags

    ingredients_text = _truncate_runtime_text(enrichment.ingredients_text, 180)
    if ingredients_text:
        gap_signals["ingredients_text"] = ingredients_text

    payload: dict[str, object] = {
        "product": product_payload,
        "derived_facts": _serialize_derived_facts(derived_output),
        "gap_signals": gap_signals or None,
    }
    if include_external_id:
        payload["product_external_id"] = product.external_id
    return payload


def _truncate_runtime_text(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    trimmed = " ".join(value.split()).strip()
    if not trimmed:
        return None
    if len(trimmed) <= limit:
        return trimmed
    return trimmed[: max(limit - 1, 1)].rstrip() + "…"


def _normalize_runtime_name(value: str | None) -> str:
    return " ".join((value or "").split()).strip().lower()


def _compact_runtime_text_list(
    values: list[str],
    *,
    limit: int,
    exclude_names: list[str | None] | None = None,
) -> list[str]:
    if limit <= 0:
        return []

    excluded = {_normalize_runtime_name(value) for value in (exclude_names or []) if value}
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        trimmed = _truncate_runtime_text(value, 80)
        normalized = _normalize_runtime_name(trimmed)
        if not trimmed or not normalized or normalized in excluded or normalized in seen:
            continue
        seen.add(normalized)
        result.append(trimmed)
        if len(result) >= limit:
            break
    return result


def _is_meaningfully_different_name(
    candidate: str | None,
    product_name: str,
    alias_names: list[str],
) -> bool:
    normalized_candidate = _normalize_runtime_name(candidate)
    if not normalized_candidate:
        return False
    comparison_names = {_normalize_runtime_name(product_name), *(_normalize_runtime_name(alias) for alias in alias_names)}
    return normalized_candidate not in comparison_names


def _select_category_hint(categories: list[str], *, limit: int) -> str | None:
    for category in reversed(categories):
        hint = _truncate_runtime_text(category, limit)
        if hint:
            return hint
    return None


def _has_strong_off_signal(
    product: Product,
    *,
    enrichment,
    derived_base: ProductClassificationOutput,
) -> bool:
    match_confidence = enrichment.match_confidence or 0.0
    if (enrichment.match_status or "") not in STRONG_OFF_MATCH_STATUSES and match_confidence < 0.96:
        return False

    ingredient_tags = list(enrichment.ingredient_tags or [])
    dietary_tags = list(enrichment.dietary_tags or [])
    allergen_tags = list(enrichment.allergen_tags or [])
    category_hint = _select_category_hint(list(enrichment.categories or []), limit=60)
    manual_tags = list(product.manual_ingredient_tags or [])

    if len(ingredient_tags) >= 2 and category_hint:
        return True
    if len(ingredient_tags) >= 3:
        return True
    if category_hint and (dietary_tags or allergen_tags):
        return True
    if manual_tags and category_hint and derived_base.food_category:
        return True
    return False


def _requires_semantic_gap_fill(product: Product, *, enrichment) -> bool:
    tokens = set(_safe_lookup_tokens(product.name))
    tokens.update(_safe_lookup_tokens(enrichment.source_product_name))
    tokens.update(_safe_lookup_tokens(" ".join(enrichment.categories or [])))
    tokens.update(_safe_lookup_tokens(" ".join((enrichment.ingredient_tags or [])[:4])))
    return bool(tokens & SEMANTIC_GAP_FILL_KEYWORDS)


def _match_derived_staple_profile(product: Product, *, enrichment) -> DerivedStapleProfile | None:
    tokens = set(_safe_lookup_tokens(product.name))
    tokens.update(_safe_lookup_tokens(enrichment.source_product_name))
    tokens.update(_safe_lookup_tokens(" ".join(enrichment.categories or [])))
    tokens.update(_safe_lookup_tokens(" ".join((enrichment.ingredient_tags or [])[:6])))
    for profile in DERIVED_STAPLE_PROFILES:
        if tokens & profile.match_tokens:
            return profile
    return None


def _build_off_derived_output(
    product: Product,
    *,
    enrichment,
    derived_profile: DerivedStapleProfile | None,
    include_semantic_defaults: bool,
) -> ProductClassificationOutput:
    ingredient_families = _derive_ingredient_families(enrichment=enrichment, derived_profile=derived_profile)
    category_hint = _select_category_hint(list(enrichment.categories or []), limit=60)
    structured_metadata = _derive_structured_metadata(
        product,
        category_hint=category_hint,
        derived_profile=derived_profile,
        include_semantic_defaults=include_semantic_defaults,
    )
    rationale = None
    confidence = None
    recipe_role_tags: list[str] = []
    substitution_groups: list[str] = []
    pantry_use_tags: list[str] = []

    if include_semantic_defaults:
        rationale = "Derived from barcode-matched Open Food Facts facts and Pantry staple rules."
        confidence = 0.84 if derived_profile is not None else 0.78
        recipe_role_tags = list(derived_profile.recipe_role_tags) if derived_profile is not None else []
        substitution_groups = list(derived_profile.substitution_groups) if derived_profile is not None else []
        pantry_use_tags = list(derived_profile.pantry_use_tags) if derived_profile is not None else []

    return ProductClassificationOutput(
        confidence=confidence,
        rationale_short=rationale,
        primary_ingredient_type=(
            derived_profile.primary_ingredient_type
            if derived_profile is not None and derived_profile.primary_ingredient_type
            else (ingredient_families[0] if ingredient_families else None)
        ),
        ingredient_families=ingredient_families,
        food_category=(
            derived_profile.food_category
            if derived_profile is not None
            else _humanize_category_hint(category_hint)
        ),
        dietary_tags=_humanize_off_tags(list(enrichment.dietary_tags or []), limit=6),
        allergen_tags=_humanize_off_tags(list(enrichment.allergen_tags or []), limit=6),
        recipe_role_tags=recipe_role_tags,
        substitution_groups=substitution_groups,
        pantry_use_tags=pantry_use_tags,
        structured_metadata=structured_metadata,
    )


def _derive_ingredient_families(*, enrichment, derived_profile: DerivedStapleProfile | None) -> list[str]:
    if derived_profile is not None and derived_profile.ingredient_family_overrides:
        return list(derived_profile.ingredient_family_overrides)

    families = _humanize_off_tags(list(enrichment.ingredient_tags or []), limit=3)
    if families:
        return families

    category_hint = _humanize_category_hint(_select_category_hint(list(enrichment.categories or []), limit=60))
    return [category_hint] if category_hint else []


def _derive_structured_metadata(
    product: Product,
    *,
    category_hint: str | None,
    derived_profile: DerivedStapleProfile | None,
    include_semantic_defaults: bool,
) -> ProductClassificationMetadataPayload:
    product_format = (
        derived_profile.product_format
        if derived_profile is not None and derived_profile.product_format
        else _infer_product_format(product.default_unit, category_hint=category_hint)
    )
    storage_profile = (
        derived_profile.storage_profile
        if derived_profile is not None and derived_profile.storage_profile
        else ("Shelf stable" if product_format is not None else None)
    )
    return ProductClassificationMetadataPayload(
        product_format=product_format,
        storage_profile=storage_profile,
        preparation_tags=list(derived_profile.preparation_tags) if include_semantic_defaults and derived_profile else [],
    )


def _serialize_derived_facts(derived_output: ProductClassificationOutput) -> dict[str, object]:
    return {
        "primary_ingredient_type": derived_output.primary_ingredient_type,
        "ingredient_families": list(derived_output.ingredient_families),
        "food_category": derived_output.food_category,
        "dietary_tags": list(derived_output.dietary_tags),
        "allergen_tags": list(derived_output.allergen_tags),
        "structured_metadata": derived_output.structured_metadata.model_dump(),
    }


def _humanize_off_tags(values: list[str], *, limit: int) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _humanize_off_value(value)
        normalized = _normalize_runtime_name(text)
        if not text or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _humanize_off_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = require_text(value.replace("_", " ").replace("-", " "), field_name="OFF tag")
    return " ".join(part.capitalize() for part in normalized.split())


def _humanize_category_hint(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _truncate_runtime_text(value, 64)
    if cleaned is None:
        return None
    return require_text(cleaned, field_name="Category")


def _infer_product_format(default_unit: str, *, category_hint: str | None) -> str | None:
    unit = _normalize_runtime_name(default_unit)
    category_text = _normalize_runtime_name(category_hint)
    if unit == "can" or "canned" in category_text or "tinned" in category_text:
        return "Canned"
    if unit == "bottle" or "bottle" in category_text:
        return "Bottled"
    if unit == "jar" or "jar" in category_text:
        return "Jarred"
    if unit in {"bag", "box", "pack"}:
        return "Dried"
    return None


def _safe_lookup_tokens(value: str | None) -> list[str]:
    if value is None or not value.strip():
        return []
    return lookup_tokens(value)
def estimate_product_intelligence_tokens(payload: object) -> int:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return max(math.ceil(len(encoded) / 4), 1)


def _build_status_counts(products: list[Product]) -> ProductIntelligenceStatusCounts:
    classified_count = 0
    stale_count = 0
    for product in products:
        intelligence = get_primary_product_intelligence(product)
        if intelligence is None:
            continue
        classified_count += 1
        if get_product_intelligence_staleness(product, intelligence).is_stale:
            stale_count += 1

    return ProductIntelligenceStatusCounts(
        total_product_count=len(products),
        classified_product_count=classified_count,
        stale_product_count=stale_count,
        unclassified_product_count=max(len(products) - classified_count, 0),
    )


def _load_household_products(db: Session, *, household: Household) -> list[Product]:
    return db.scalars(
        select(Product)
        .where(Product.household_id == household.id)
        .options(
            selectinload(Product.aliases),
            selectinload(Product.barcodes),
            selectinload(Product.enrichments),
            selectinload(Product.intelligence_records),
        )
        .order_by(Product.name)
    ).all()


def _load_target_products(
    db: Session,
    *,
    household: Household,
    request: ProductIntelligenceRunRequest,
) -> list[Product]:
    products = _load_household_products(db, household=household)
    if request.mode == "product":
        if not request.product_external_id:
            raise ValueError("product_external_id is required when mode is product.")
        selected = [product for product in products if product.external_id == request.product_external_id]
        if not selected:
            raise ValueError("Product not found.")
        return selected
    return products


def _get_product_by_id(
    db: Session,
    *,
    household: Household,
    product_id,
) -> Product | None:
    return db.scalar(
        select(Product)
        .where(Product.household_id == household.id)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.aliases),
            selectinload(Product.barcodes),
            selectinload(Product.enrichments),
            selectinload(Product.intelligence_records),
        )
    )


def _classify_product(
    db: Session,
    *,
    household: Household,
    actor: User,
    product: Product,
    adapter,
    model: str,
    provider_type: str,
) -> ProductIntelligence:
    trim_level = get_product_intelligence_runtime_trim_level(
        product,
        provider_type=provider_type,
        model=model,
    )
    plan = build_product_intelligence_execution_plan(
        product,
        provider_type=provider_type,
        model=model,
        trim_level=trim_level,
        include_external_id=False,
    )
    if plan.strategy == PRODUCT_INTELLIGENCE_EXECUTION_DERIVED_ONLY and plan.derived_output is not None:
        return apply_product_intelligence_classification(
            db,
            household=household,
            actor=actor,
            product=product,
            parsed=plan.derived_output,
            model=None,
            provider_type=PRODUCT_INTELLIGENCE_SOURCE_PROVIDER_DERIVED,
        )

    completion = adapter.generate_structured_output(
        StructuredCompletionRequest(
            model=model,
            system_prompt=(
                "You classify pantry products into structured recipe-matching metadata. "
                "Base every field only on the supplied product evidence. "
                "Each product includes a classification_strategy. "
                "When classification_strategy is ai_gap_fill, trust derived_facts for factual fields "
                "such as category, ingredient families, allergens, dietary tags, product format, "
                "and storage profile. Use AI mainly for recipe roles, substitution groups, pantry uses, "
                "cuisine, flavour, preparation, confidence, and a short rationale. "
                "Prefer empty values over guesses. "
                "Keep rationale_short under 160 characters. "
                "Use short human-readable tags and categories. "
                "Return valid JSON only."
            ),
            user_payload={
                "task": "Classify this pantry product for recipe matching and pantry suggestions.",
                "classification_scope": PRODUCT_INTELLIGENCE_SCOPE,
                "classification_version": PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
                "schema_version": PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
                "guidance": {
                    "food_category": "Choose one concise food category.",
                    "recipe_role_tags": [
                        "protein",
                        "vegetable",
                        "carbohydrate",
                        "seasoning",
                        "sauce",
                        "aromatic",
                        "acid",
                        "sweetener",
                        "fat",
                        "stock",
                        "base",
                        "baking",
                        "garnish",
                        "snack",
                    ],
                    "pantry_use_tags": [
                        "pantry_staple",
                        "quick_meal",
                        "shelf_stable",
                        "freezer_friendly",
                        "baking",
                        "snacking",
                        "bulk_cooking",
                        "sauce_builder",
                        "breakfast",
                        "side_dish",
                    ],
                },
                "product": plan.ai_payload or plan.source_payload,
            },
            output_schema=ProductClassificationOutput.model_json_schema(),
        )
    )
    parsed = ProductClassificationOutput.model_validate(completion.parsed_output)
    if plan.strategy == PRODUCT_INTELLIGENCE_EXECUTION_AI_GAP_FILL and plan.derived_output is not None:
        parsed = merge_gap_fill_product_classification(parsed, derived_output=plan.derived_output)

    return apply_product_intelligence_classification(
        db,
        household=household,
        actor=actor,
        product=product,
        parsed=parsed,
        model=model,
        provider_type=provider_type,
    )


def apply_product_intelligence_classification(
    db: Session,
    *,
    household: Household,
    actor: User,
    product: Product,
    parsed: ProductClassificationOutput,
    model: str | None,
    provider_type: str,
) -> ProductIntelligence:
    intelligence = get_primary_product_intelligence(product)
    if intelligence is None:
        intelligence = ProductIntelligence(
            household_id=household.id,
            product_id=product.id,
            source_provider=provider_type,
            classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
            classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
            schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
            source_data_hash=build_product_intelligence_source_data_hash(
                product,
                provider_type=provider_type,
                model=model,
            ),
            classified_at=utc_now(),
        )
        db.add(intelligence)

    intelligence.source_provider = provider_type
    intelligence.source_model = model
    intelligence.classification_scope = PRODUCT_INTELLIGENCE_SCOPE
    intelligence.classification_version = PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION
    intelligence.schema_version = PRODUCT_INTELLIGENCE_SCHEMA_VERSION
    intelligence.source_data_hash = build_product_intelligence_source_data_hash(
        product,
        provider_type=provider_type,
        model=model,
    )
    intelligence.classified_at = utc_now()
    intelligence.confidence = parsed.confidence
    intelligence.rationale_short = _normalize_optional_text(parsed.rationale_short, field_name="Rationale", max_length=320)
    intelligence.primary_ingredient_type = _normalize_optional_text(
        parsed.primary_ingredient_type,
        field_name="Primary ingredient type",
        max_length=128,
    )
    intelligence.ingredient_families = _normalize_tags(parsed.ingredient_families, field_name="Ingredient family")
    intelligence.food_category = _normalize_optional_text(parsed.food_category, field_name="Food category", max_length=128)
    intelligence.dietary_tags = _normalize_tags(parsed.dietary_tags, field_name="Dietary tag")
    intelligence.allergen_tags = _normalize_tags(parsed.allergen_tags, field_name="Allergen tag")
    intelligence.recipe_role_tags = _normalize_tags(parsed.recipe_role_tags, field_name="Recipe role")
    intelligence.substitution_groups = _normalize_tags(parsed.substitution_groups, field_name="Substitution group")
    intelligence.pantry_use_tags = _normalize_tags(parsed.pantry_use_tags, field_name="Pantry use tag")
    intelligence.structured_metadata = _normalize_structured_metadata(parsed.structured_metadata)

    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="product.intelligence.classified",
        target_type="product",
        target_external_id=product.external_id,
        event_metadata={
            "product_name": product.name,
            "provider_type": provider_type,
            "default_model": model,
            "classification_scope": PRODUCT_INTELLIGENCE_SCOPE,
            "classification_version": PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
            "schema_version": PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
            "food_category": intelligence.food_category,
            "primary_ingredient_type": intelligence.primary_ingredient_type,
            "confidence": intelligence.confidence,
        },
    )
    db.flush()
    return intelligence


def merge_gap_fill_product_classification(
    parsed: ProductClassificationOutput,
    *,
    derived_output: ProductClassificationOutput,
) -> ProductClassificationOutput:
    return ProductClassificationOutput(
        confidence=parsed.confidence,
        rationale_short=parsed.rationale_short,
        primary_ingredient_type=derived_output.primary_ingredient_type or parsed.primary_ingredient_type,
        ingredient_families=(
            list(derived_output.ingredient_families)
            if derived_output.ingredient_families
            else list(parsed.ingredient_families)
        ),
        food_category=derived_output.food_category or parsed.food_category,
        dietary_tags=list(derived_output.dietary_tags) if derived_output.dietary_tags else list(parsed.dietary_tags),
        allergen_tags=list(derived_output.allergen_tags) if derived_output.allergen_tags else list(parsed.allergen_tags),
        recipe_role_tags=list(parsed.recipe_role_tags),
        substitution_groups=list(parsed.substitution_groups),
        pantry_use_tags=list(parsed.pantry_use_tags),
        structured_metadata=ProductClassificationMetadataPayload(
            product_format=(
                derived_output.structured_metadata.product_format
                or parsed.structured_metadata.product_format
            ),
            storage_profile=(
                derived_output.structured_metadata.storage_profile
                or parsed.structured_metadata.storage_profile
            ),
            cuisine_tags=list(parsed.structured_metadata.cuisine_tags),
            flavour_tags=list(parsed.structured_metadata.flavour_tags),
            preparation_tags=list(parsed.structured_metadata.preparation_tags),
        ),
    )


def _normalize_optional_text(value: str | None, *, field_name: str, max_length: int) -> str | None:
    if value is None or not value.strip():
        return None
    return require_text(value, field_name=field_name)[:max_length]


def _normalize_tags(values: list[str], *, field_name: str) -> list[str]:
    return normalize_text_tags(values[:10], field_name=field_name)


def _normalize_structured_metadata(payload: ProductClassificationMetadataPayload) -> dict[str, object]:
    return cast(
        dict[str, object],
        ProductIntelligenceStructuredMetadata(
            product_format=_normalize_optional_text(payload.product_format, field_name="Product format", max_length=64),
            storage_profile=_normalize_optional_text(
                payload.storage_profile,
                field_name="Storage profile",
                max_length=64,
            ),
            cuisine_tags=_normalize_tags(payload.cuisine_tags, field_name="Cuisine tag"),
            flavour_tags=_normalize_tags(payload.flavour_tags, field_name="Flavour tag"),
            preparation_tags=_normalize_tags(payload.preparation_tags, field_name="Preparation tag"),
        ).model_dump(),
    )


def _build_latest_run_summary(db: Session, *, household: Household):
    from app.services.product_intelligence_runs import get_latest_product_intelligence_run_summary

    return get_latest_product_intelligence_run_summary(db, household=household)
