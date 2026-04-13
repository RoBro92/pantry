from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import cast

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.ai import AI_HEALTH_UNHEALTHY
from app.models.base import utc_now
from app.models.household import Household
from app.models.product import Product
from app.models.product_intelligence import ProductIntelligence
from app.models.user import User
from app.schemas.pantry import (
    ProductIntelligenceRunItem,
    ProductIntelligenceRunRequest,
    ProductIntelligenceRunResponse,
    ProductIntelligenceStatusCounts,
    ProductIntelligenceStatusResponse,
    ProductIntelligenceStructuredMetadata,
    ProductIntelligenceSummary,
)
from app.services.ai_config import get_ai_feature_enabled, refresh_provider_health, resolve_provider_config
from app.services.ai_providers import StructuredCompletionRequest, build_ai_provider_adapter
from app.services.ai_runtime_errors import AIUserFacingError, summarize_ai_failure
from app.services.audit import record_audit_event
from app.services.pantry_normalization import normalize_text_tags, require_text
from app.services.product_enrichment import get_primary_enrichment

PRODUCT_INTELLIGENCE_SCOPE = "pantry_product_classification"
PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION = "v1"
PRODUCT_INTELLIGENCE_SCHEMA_VERSION = "2026-04-10"
PRODUCT_INTELLIGENCE_STALE_SCHEMA = "schema_changed"
PRODUCT_INTELLIGENCE_STALE_CLASSIFIER = "classification_version_changed"
PRODUCT_INTELLIGENCE_STALE_SOURCE = "source_product_data_changed"


class ProductClassificationMetadataPayload(BaseModel):
    product_format: str | None = None
    storage_profile: str | None = None
    cuisine_tags: list[str] = Field(default_factory=list)
    flavour_tags: list[str] = Field(default_factory=list)
    preparation_tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


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

    if not get_ai_feature_enabled():
        return ProductIntelligenceStatusResponse(
            available=False,
            reason="AI features are disabled for this deployment.",
            counts=counts,
            classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
            classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
            schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
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
        )

    record = resolved.record
    if not record.is_enabled:
        return ProductIntelligenceStatusResponse(
            available=False,
            reason="The configured AI provider is disabled.",
            provider_type=record.provider_type,
            default_model=record.default_model,
            health_status=record.health_status,
            counts=counts,
            classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
            classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
            schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
        )

    if record.health_status == AI_HEALTH_UNHEALTHY:
        return ProductIntelligenceStatusResponse(
            available=False,
            reason=record.health_error or "The configured AI provider is unhealthy.",
            provider_type=record.provider_type,
            default_model=record.default_model,
            health_status=record.health_status,
            counts=counts,
            classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
            classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
            schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
        )

    return ProductIntelligenceStatusResponse(
        available=True,
        provider_type=record.provider_type,
        default_model=record.default_model,
        health_status=record.health_status,
        counts=counts,
        classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
        classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
        schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
    )


def run_product_intelligence_classification(
    db: Session,
    *,
    household: Household,
    actor: User,
    request: ProductIntelligenceRunRequest,
) -> ProductIntelligenceRunResponse:
    status = build_product_intelligence_status(db, household=household)
    if not status.available:
        raise ValueError(status.reason or "AI product intelligence is unavailable.")

    resolved = resolve_provider_config(db, household=household)
    if resolved is None:
        raise ValueError("No AI provider is configured for this installation.")

    health = refresh_provider_health(db, config=resolved.record)
    if not health.is_healthy:
        raise AIUserFacingError(health.message or "The AI provider is unavailable.", status_code=503)

    products = _load_target_products(db, household=household, request=request)
    adapter = build_ai_provider_adapter(resolved.runtime)
    started_at = utc_now()
    items: list[ProductIntelligenceRunItem] = []
    classified_count = 0
    skipped_count = 0
    failed_count = 0
    stale_reclassified_count = 0

    for product in products:
        intelligence = get_primary_product_intelligence(product)
        staleness = get_product_intelligence_staleness(product, intelligence)

        if request.mode == "unclassified" and intelligence is not None:
            skipped_count += 1
            items.append(
                ProductIntelligenceRunItem(
                    product_external_id=product.external_id,
                    product_name=product.name,
                    status="skipped",
                    message="Product already has AI classification attached.",
                    stale_before_run=staleness.is_stale,
                    intelligence=serialize_product_intelligence(intelligence, product=product),
                )
            )
            continue

        try:
            updated = _classify_product(
                db,
                household=household,
                actor=actor,
                product=product,
                adapter=adapter,
                model=resolved.record.default_model,
                provider_type=resolved.record.provider_type,
            )
            db.commit()
            db.expire_all()
        except Exception as exc:
            db.rollback()
            failed_count += 1
            user_message, _, _ = summarize_ai_failure(
                exc,
                fallback_message="The AI provider could not classify this product.",
            )
            items.append(
                ProductIntelligenceRunItem(
                    product_external_id=product.external_id,
                    product_name=product.name,
                    status="failed",
                    message=user_message,
                    stale_before_run=staleness.is_stale,
                )
            )
            continue

        refreshed = _get_product_by_id(db, household=household, product_id=product.id) or product
        refreshed_intelligence = get_primary_product_intelligence(refreshed)
        classified_count += 1
        if intelligence is not None and staleness.is_stale:
            stale_reclassified_count += 1
        items.append(
            ProductIntelligenceRunItem(
                product_external_id=refreshed.external_id,
                product_name=refreshed.name,
                status="reclassified" if intelligence is not None else "classified",
                message="AI product intelligence saved.",
                confidence=refreshed_intelligence.confidence if refreshed_intelligence is not None else None,
                stale_before_run=staleness.is_stale,
                intelligence=serialize_product_intelligence(refreshed_intelligence, product=refreshed),
            )
        )

    completed_at = utc_now()
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="product.intelligence.run.completed",
        target_type="household",
        target_external_id=household.external_id,
        event_metadata={
            "mode": request.mode,
            "provider_type": resolved.record.provider_type,
            "default_model": resolved.record.default_model,
            "total_candidates": len(products),
            "classified_count": classified_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "stale_reclassified_count": stale_reclassified_count,
        },
    )
    db.commit()

    return ProductIntelligenceRunResponse(
        mode=request.mode,
        available=True,
        provider_type=resolved.record.provider_type,
        default_model=resolved.record.default_model,
        classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
        classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
        schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
        total_candidates=len(products),
        classified_count=classified_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        stale_reclassified_count=stale_reclassified_count,
        items=items,
        started_at=started_at,
        completed_at=completed_at,
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
    if intelligence.source_data_hash != build_product_intelligence_source_data_hash(product):
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


def build_product_intelligence_source_data_hash(product: Product) -> str:
    payload = build_product_intelligence_source_payload(product)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_product_intelligence_source_payload(product: Product) -> dict[str, object]:
    enrichment = get_primary_enrichment(product)
    nutrition_summary: list[dict[str, object]] = []
    if enrichment and enrichment.nutrition_summary:
        for item in enrichment.nutrition_summary[:6]:
            if isinstance(item, dict):
                nutrition_summary.append(
                    {
                        "label": item.get("label"),
                        "value": item.get("value"),
                        "unit": item.get("unit"),
                    }
                )

    compact_nutriments: dict[str, object] = {}
    if enrichment and enrichment.nutriments_payload:
        for key in sorted(enrichment.nutriments_payload.keys())[:10]:
            compact_nutriments[key] = enrichment.nutriments_payload[key]

    return {
        "product": {
            "name": product.name,
            "default_unit": product.default_unit,
            "aliases": [alias.name for alias in product.aliases][:12],
            "barcodes": [barcode.value for barcode in product.barcodes][:8],
            "notes": product.notes,
            "manual_ingredient_tags": list(product.manual_ingredient_tags or [])[:12],
        },
        "enrichment": (
            {
                "source_name": enrichment.source_name,
                "source_product_name": enrichment.source_product_name,
                "ingredient_tags": list(enrichment.ingredient_tags or [])[:14],
                "ingredient_tokens": list(enrichment.ingredient_tokens or [])[:18],
                "ingredients_text": (enrichment.ingredients_text or "")[:500] or None,
                "allergen_tags": list(enrichment.allergen_tags or [])[:10],
                "trace_tags": list(enrichment.trace_tags or [])[:10],
                "dietary_tags": list(enrichment.dietary_tags or [])[:10],
                "labels": list(enrichment.labels or [])[:10],
                "categories": list(enrichment.categories or [])[:10],
                "nutrition_summary": nutrition_summary,
                "nutriments": compact_nutriments,
            }
            if enrichment is not None
            else None
        ),
    }


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
    payload = build_product_intelligence_source_payload(product)
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

    intelligence = get_primary_product_intelligence(product)
    if intelligence is None:
        intelligence = ProductIntelligence(
            household_id=household.id,
            product_id=product.id,
            source_provider=provider_type,
            classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
            classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
            schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
            source_data_hash=build_product_intelligence_source_data_hash(product),
            classified_at=utc_now(),
        )
        db.add(intelligence)

    intelligence.source_provider = provider_type
    intelligence.source_model = model
    intelligence.classification_scope = PRODUCT_INTELLIGENCE_SCOPE
    intelligence.classification_version = PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION
    intelligence.schema_version = PRODUCT_INTELLIGENCE_SCHEMA_VERSION
    intelligence.source_data_hash = build_product_intelligence_source_data_hash(product)
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
