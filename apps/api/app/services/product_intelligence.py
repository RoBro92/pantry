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
from app.services.pantry_normalization import normalize_text_tags, require_text
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
    return _build_product_intelligence_runtime_payload(
        product,
        trim_level=trim_level,
        include_external_id=False,
    )


def build_product_intelligence_batch_source_payload(
    product: Product,
    *,
    trim_level: int = 0,
) -> dict[str, object]:
    return _build_product_intelligence_runtime_payload(
        product,
        trim_level=trim_level,
        include_external_id=True,
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
        payload = _build_product_intelligence_runtime_payload(
            product,
            trim_level=trim_level,
            include_external_id=True,
        )
        if estimate_product_intelligence_tokens(payload) <= per_product_budget:
            return trim_level
    return PRODUCT_INTELLIGENCE_MAX_TRIM_LEVEL


def _build_product_intelligence_runtime_payload(
    product: Product,
    *,
    trim_level: int,
    include_external_id: bool,
) -> dict[str, object]:
    enrichment = get_primary_enrichment(product)
    alias_limit = 4 if trim_level == 0 else 2 if trim_level == 1 else 1
    notes_limit = 180 if trim_level == 0 else 120 if trim_level == 1 else 80
    manual_tag_limit = 10 if trim_level == 0 else 6 if trim_level == 1 else 4
    ingredient_tag_limit = 14 if trim_level == 0 else 9 if trim_level == 1 else 5
    dietary_tag_limit = 8 if trim_level == 0 else 6 if trim_level == 1 else 4
    allergen_tag_limit = 8 if trim_level == 0 else 6 if trim_level == 1 else 4
    ingredients_text_limit = 240 if trim_level == 0 else 140 if trim_level == 1 else 90
    category_hint_limit = 60 if trim_level == 0 else 40 if trim_level == 1 else 28

    manual_tags = list(product.manual_ingredient_tags or [])[:manual_tag_limit]
    alias_names = _compact_runtime_text_list(
        [alias.name for alias in product.aliases],
        limit=alias_limit,
        exclude_names=[product.name, enrichment.source_product_name if enrichment else None],
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

    payload: dict[str, object] = {"product": product_payload}
    if include_external_id:
        payload["product_external_id"] = product.external_id

    if enrichment is None:
        payload["enrichment"] = None
        return payload

    ingredient_tags = _compact_runtime_text_list(
        list(enrichment.ingredient_tags or []),
        limit=ingredient_tag_limit,
    )
    dietary_tags = _compact_runtime_text_list(
        list(enrichment.dietary_tags or []),
        limit=dietary_tag_limit,
    )
    allergen_tags = _compact_runtime_text_list(
        list(enrichment.allergen_tags or []),
        limit=allergen_tag_limit,
    )
    ingredient_signal_count = len(ingredient_tags) + len(manual_tags)
    enrichment_payload: dict[str, object] = {}

    source_product_name = _truncate_runtime_text(enrichment.source_product_name, notes_limit)
    if _is_meaningfully_different_name(source_product_name, product.name, alias_names):
        enrichment_payload["source_product_name"] = source_product_name
    if ingredient_tags:
        enrichment_payload["ingredient_tags"] = ingredient_tags
    if dietary_tags:
        enrichment_payload["dietary_tags"] = dietary_tags
    if allergen_tags:
        enrichment_payload["allergen_tags"] = allergen_tags

    category_hint = _select_category_hint(list(enrichment.categories or []), limit=category_hint_limit)
    if category_hint:
        enrichment_payload["category_hint"] = category_hint

    ingredients_text = _truncate_runtime_text(enrichment.ingredients_text, ingredients_text_limit)
    if ingredients_text and ingredient_signal_count < 2:
        enrichment_payload["ingredients_text"] = ingredients_text

    payload["enrichment"] = enrichment_payload or None
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
    payload = build_product_intelligence_source_payload(
        product,
        provider_type=provider_type,
        model=model,
    )
    completion = adapter.generate_structured_output(
        StructuredCompletionRequest(
            model=model,
            system_prompt=(
                "You classify pantry products into structured recipe-matching metadata. "
                "Base every field only on the supplied product evidence. "
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
                "product": payload,
            },
            output_schema=ProductClassificationOutput.model_json_schema(),
        )
    )
    parsed = ProductClassificationOutput.model_validate(completion.parsed_output)

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
    model: str,
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
