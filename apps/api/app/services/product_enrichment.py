from __future__ import annotations

from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.barcode import Barcode
from app.models.base import utc_now
from app.models.household import Household
from app.models.product import Product
from app.models.product_enrichment import ProductEnrichment
from app.models.user import User
from app.schemas.pantry import (
    ConfirmedProductEnrichmentRequest,
    ProductEnrichmentPreviewResponse,
    ProductEnrichmentSummary,
    ProductSummary,
)
from app.services.audit import record_audit_event
from app.services.open_food_facts import (
    OPEN_FOOD_FACTS_SOURCE,
    OpenFoodFactsClient,
    OpenFoodFactsUnavailableError,
)
from app.services.pantry_normalization import normalize_barcode


class ProductEnrichmentError(ValueError):
    pass


def get_default_open_food_facts_client() -> OpenFoodFactsClient:
    return OpenFoodFactsClient()


def get_primary_enrichment(product: Product, *, source_name: str = OPEN_FOOD_FACTS_SOURCE) -> ProductEnrichment | None:
    for enrichment in product.enrichments:
        if enrichment.source_name == source_name:
            return enrichment
    return product.enrichments[0] if product.enrichments else None


def serialize_product_enrichment(enrichment: ProductEnrichment | None) -> ProductEnrichmentSummary | None:
    if enrichment is None:
        return None
    return ProductEnrichmentSummary(
        source_name=enrichment.source_name,
        source_product_id=enrichment.source_product_id,
        source_barcode=enrichment.source_barcode,
        source_product_name=enrichment.source_product_name,
        source_product_url=enrichment.source_product_url,
        product_image_url=enrichment.product_image_url,
        enrichment_status=enrichment.enrichment_status,
        ingredients_text=enrichment.ingredients_text,
        ingredient_tags=list(enrichment.ingredient_tags or []),
        ingredient_tokens=list(enrichment.ingredient_tokens or []),
        allergens_text=enrichment.allergens_text,
        traces_text=enrichment.traces_text,
        allergen_tags=list(enrichment.allergen_tags or []),
        trace_tags=list(enrichment.trace_tags or []),
        dietary_tags=list(enrichment.dietary_tags or []),
        nutriments_payload=cast(dict, enrichment.nutriments_payload or {}),
        nutrition_summary=cast(list, enrichment.nutrition_summary or []),
        nutrition_summary_text=enrichment.nutrition_summary_text,
        labels=list(enrichment.labels or []),
        categories=list(enrichment.categories or []),
        match_status=enrichment.match_status,
        match_confidence=enrichment.match_confidence,
        last_synced_at=enrichment.last_synced_at,
        attribution=cast(dict, enrichment.source_attribution or {}),
    )


def serialize_product_summary(product: Product) -> ProductSummary:
    return ProductSummary(
        external_id=product.external_id,
        name=product.name,
        default_unit=product.default_unit,
        aliases=[alias.name for alias in product.aliases],
        barcodes=[barcode.value for barcode in product.barcodes],
        manual_ingredient_tags=list(product.manual_ingredient_tags or []),
        enrichment=serialize_product_enrichment(get_primary_enrichment(product)),
    )


def refresh_product_with_enrichment(
    db: Session,
    *,
    household: Household,
    external_id: str,
) -> Product | None:
    return db.scalar(
        select(Product)
        .where(Product.household_id == household.id)
        .where(Product.external_id == external_id)
    )


def preview_product_enrichment(
    *,
    product_name: str,
    barcode: str | None,
    client: OpenFoodFactsClient | None = None,
) -> ProductEnrichmentPreviewResponse:
    off_client = client or get_default_open_food_facts_client()

    if barcode:
        try:
            barcode_candidate = off_client.lookup_by_barcode(barcode)
        except OpenFoodFactsUnavailableError as exc:
            if not product_name.strip():
                return ProductEnrichmentPreviewResponse(
                    query_name=product_name,
                    query_barcode=barcode,
                    lookup_strategy="barcode",
                    status="unavailable",
                    message=str(exc),
                )
        else:
            if barcode_candidate is not None:
                return ProductEnrichmentPreviewResponse(
                    query_name=product_name,
                    query_barcode=barcode,
                    lookup_strategy="barcode",
                    status="matched",
                    message="Found an Open Food Facts product for this barcode.",
                    candidates=[barcode_candidate],
                )

    if not product_name.strip():
        return ProductEnrichmentPreviewResponse(
            query_name=product_name,
            query_barcode=barcode,
            lookup_strategy="barcode" if barcode else "name_search",
            status="no_match",
            message="Enter a product name to search Open Food Facts.",
        )

    try:
        candidates = off_client.search_by_name(product_name)
    except OpenFoodFactsUnavailableError as exc:
        return ProductEnrichmentPreviewResponse(
            query_name=product_name,
            query_barcode=barcode,
            lookup_strategy="barcode_then_name_search" if barcode else "name_search",
            status="unavailable",
            message=str(exc),
        )

    if not candidates:
        return ProductEnrichmentPreviewResponse(
            query_name=product_name,
            query_barcode=barcode,
            lookup_strategy="barcode_then_name_search" if barcode else "name_search",
            status="no_match",
            message=(
                "No Open Food Facts matches were found for this barcode or name."
                if barcode
                else "No Open Food Facts matches were found for this name."
            ),
        )

    return ProductEnrichmentPreviewResponse(
        query_name=product_name,
        query_barcode=barcode,
        lookup_strategy="barcode_then_name_search" if barcode else "name_search",
        status="matched" if len(candidates) == 1 else "multiple_matches",
        message=(
            "Barcode lookup did not find a product, so these name-search matches are lower confidence."
            if barcode
            else "Review these Open Food Facts matches before linking one."
        ),
        candidates=candidates,
    )


def apply_confirmed_product_enrichment(
    db: Session,
    *,
    household: Household,
    actor: User,
    product: Product,
    confirmed_enrichment: ConfirmedProductEnrichmentRequest | None,
    client: OpenFoodFactsClient | None = None,
) -> ProductEnrichment | None:
    if confirmed_enrichment is None:
        return None
    if confirmed_enrichment.source_name != OPEN_FOOD_FACTS_SOURCE:
        raise ProductEnrichmentError("Unsupported enrichment source.")

    off_client = client or get_default_open_food_facts_client()
    try:
        candidate = off_client.fetch_product_by_id(confirmed_enrichment.source_product_id)
    except OpenFoodFactsUnavailableError as exc:
        raise ProductEnrichmentError(str(exc)) from exc

    if candidate is None:
        raise ProductEnrichmentError("The selected Open Food Facts product is no longer available.")

    enrichment = db.scalar(
        select(ProductEnrichment)
        .where(ProductEnrichment.product_id == product.id)
        .where(ProductEnrichment.source_name == OPEN_FOOD_FACTS_SOURCE)
    )
    if enrichment is None:
        enrichment = ProductEnrichment(
            household_id=household.id,
            product_id=product.id,
            source_name=OPEN_FOOD_FACTS_SOURCE,
            source_product_id=candidate.source_product_id,
        )
        db.add(enrichment)

    enrichment.source_product_id = candidate.source_product_id
    enrichment.source_barcode = candidate.source_barcode
    enrichment.source_product_name = candidate.source_product_name
    enrichment.source_product_url = candidate.source_product_url
    enrichment.product_image_url = candidate.product_image_url
    enrichment.enrichment_status = "linked"
    enrichment.ingredients_text = candidate.ingredients_text
    enrichment.ingredient_tags = list(candidate.ingredient_tags)
    enrichment.ingredient_tokens = list(candidate.ingredient_tokens)
    enrichment.allergens_text = candidate.allergens_text
    enrichment.traces_text = candidate.traces_text
    enrichment.allergen_tags = list(candidate.allergen_tags)
    enrichment.trace_tags = list(candidate.trace_tags)
    enrichment.dietary_tags = list(candidate.dietary_tags)
    enrichment.nutriments_payload = dict(candidate.nutriments_payload)
    enrichment.nutrition_summary = [item.model_dump() for item in candidate.nutrition_summary]
    enrichment.nutrition_summary_text = candidate.nutrition_summary_text
    enrichment.labels = list(candidate.labels)
    enrichment.categories = list(candidate.categories)
    enrichment.match_status = confirmed_enrichment.match_status or candidate.match_status
    enrichment.match_confidence = _derive_match_confidence(product.name, candidate.source_product_name, enrichment.match_status)
    enrichment.source_attribution = candidate.attribution.model_dump()
    enrichment.last_synced_at = utc_now()

    _attach_confirmed_barcode(db, household=household, product=product, barcode_value=candidate.source_barcode)

    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="product.enrichment_synced",
        target_type="product",
        target_external_id=product.external_id,
        event_metadata={
            "product_name": product.name,
            "source_name": OPEN_FOOD_FACTS_SOURCE,
            "source_product_id": candidate.source_product_id,
            "source_product_name": candidate.source_product_name,
            "match_status": enrichment.match_status,
        },
    )
    db.flush()
    return enrichment


def _derive_match_confidence(product_name: str, source_product_name: str | None, match_status: str | None) -> float | None:
    if match_status == "barcode_exact":
        return 1.0
    if source_product_name is None:
        return None
    normalized_product_name = product_name.strip().lower()
    normalized_source_name = source_product_name.strip().lower()
    if normalized_product_name == normalized_source_name:
        return 0.96
    if normalized_product_name in normalized_source_name or normalized_source_name in normalized_product_name:
        return 0.82
    return 0.68


def _attach_confirmed_barcode(
    db: Session,
    *,
    household: Household,
    product: Product,
    barcode_value: str | None,
) -> None:
    if barcode_value is None:
        return
    normalized_value = normalize_barcode(barcode_value)
    if any(barcode.normalized_value == normalized_value for barcode in product.barcodes):
        return

    existing_barcode = db.scalar(
        select(Barcode)
        .where(Barcode.household_id == household.id)
        .where(Barcode.normalized_value == normalized_value)
    )
    if existing_barcode is not None:
        return

    barcode = Barcode(
        household_id=household.id,
        product_id=product.id,
        value=normalized_value,
        normalized_value=normalized_value,
    )
    db.add(barcode)
    product.barcodes.append(barcode)
