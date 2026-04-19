from __future__ import annotations

from dataclasses import dataclass

from app.schemas.ai import AISuggestionContextSnapshot, AISuggestionRequest
from app.services.ai_runtime import estimate_ai_payload_tokens
from app.services.pantry_queries import PantryFilterOptions, build_near_expiry_response, build_pantry_overview
from app.services.recipe_queries import build_recipe_detail_response, build_recipe_list_response
from app.services.tenancy import HouseholdAccess

AI_CONTEXT_MAX_CLASSIFIED_PRODUCTS = 20
AI_CONTEXT_MAX_FALLBACK_PRODUCTS = 16
AI_CONTEXT_MAX_STOCK_LOTS = 12
AI_CONTEXT_MAX_NEAR_EXPIRY_LOTS = 8
AI_CONTEXT_MAX_RECIPES = 6
AI_CONTEXT_MAX_RECIPE_INGREDIENTS = 12


@dataclass(frozen=True)
class AIContextBundle:
    payload: dict[str, object]
    snapshot: AISuggestionContextSnapshot
    diagnostics: dict[str, object]


def _trim_text(value: str | None, *, limit: int) -> str | None:
    if value is None:
        return None
    stripped = " ".join(value.split()).strip()
    if not stripped:
        return None
    if len(stripped) <= limit:
        return stripped
    return stripped[: max(limit - 1, 1)].rstrip() + "…"


def _serialize_focused_recipe(recipe_detail) -> dict[str, object]:
    return {
        "external_id": recipe_detail.external_id,
        "title": recipe_detail.title,
        "notes": _trim_text(recipe_detail.notes, limit=120),
        "source_kind": recipe_detail.source_kind,
        "ingredient_count": recipe_detail.ingredient_count,
        "pantry_coverage": recipe_detail.pantry_coverage.model_dump(mode="json"),
        "ingredients": [
            {
                "name": ingredient.name,
                "quantity": str(ingredient.quantity),
                "unit": ingredient.unit,
                "note": _trim_text(ingredient.note, limit=60),
                "match_source": ingredient.match_source,
                "product_name": ingredient.product.name if ingredient.product is not None else None,
                "coverage_status": ingredient.coverage.status,
                "missing_quantity": str(ingredient.coverage.missing_quantity),
            }
            for ingredient in recipe_detail.ingredients[:AI_CONTEXT_MAX_RECIPE_INGREDIENTS]
        ],
    }


def build_household_ai_context(
    db,
    *,
    access: HouseholdAccess,
    request: AISuggestionRequest,
) -> AIContextBundle:
    pantry_overview = build_pantry_overview(db, access=access, filters=PantryFilterOptions())
    near_expiry = build_near_expiry_response(db, access=access, days=7)
    recipe_list = build_recipe_list_response(db, access=access)
    recipe_detail = None
    classified_products = []
    fallback_products = []

    for product in pantry_overview.products[: AI_CONTEXT_MAX_CLASSIFIED_PRODUCTS + AI_CONTEXT_MAX_FALLBACK_PRODUCTS]:
        base_product = {
            "product_external_id": product.product_external_id,
            "product_name": product.product_name,
            "unit": product.unit,
            "total_quantity": str(product.total_quantity),
            "stock_status": product.stock_status,
            "near_expiry_lot_count": product.near_expiry_lot_count,
            "nearest_expiry_on": product.nearest_expiry_on,
        }
        if product.intelligence is not None:
            if len(classified_products) >= AI_CONTEXT_MAX_CLASSIFIED_PRODUCTS:
                continue
            classified_products.append(
                {
                    **base_product,
                    "food_category": product.intelligence.food_category,
                    "primary_ingredient_type": product.intelligence.primary_ingredient_type,
                    "ingredient_families": product.intelligence.ingredient_families[:5],
                    "dietary_tags": product.intelligence.dietary_tags[:6],
                    "allergen_tags": product.intelligence.allergen_tags[:6],
                    "recipe_role_tags": product.intelligence.recipe_role_tags[:6],
                    "substitution_groups": product.intelligence.substitution_groups[:6],
                    "pantry_use_tags": product.intelligence.pantry_use_tags[:6],
                    "structured_metadata": {
                        "product_format": product.intelligence.structured_metadata.product_format,
                        "storage_profile": product.intelligence.structured_metadata.storage_profile,
                        "preparation_tags": product.intelligence.structured_metadata.preparation_tags[:4],
                    },
                    "is_stale": product.intelligence.is_stale,
                }
            )
        else:
            if len(fallback_products) >= AI_CONTEXT_MAX_FALLBACK_PRODUCTS:
                continue
            enrichment_payload = (
                {
                    "ingredient_tags": product.enrichment.ingredient_tags[:8],
                    "dietary_tags": product.enrichment.dietary_tags[:6],
                    "allergen_tags": product.enrichment.allergen_tags[:6],
                    "categories": product.enrichment.categories[:6],
                }
                if product.enrichment is not None
                else None
            )
            fallback_products.append(
                {
                    **base_product,
                    "manual_ingredient_tags": product.manual_ingredient_tags[:6],
                    "aliases": product.aliases[:4],
                    "notes": (
                        _trim_text(product.notes, limit=120)
                        if not product.manual_ingredient_tags and enrichment_payload is None
                        else None
                    ),
                    "enrichment": enrichment_payload,
                }
            )

    if request.recipe_external_id:
        recipe_detail = build_recipe_detail_response(
            db,
            access=access,
            recipe_external_id=request.recipe_external_id,
        ).recipe

    payload = {
        "household": {
            "external_id": access.household.external_id,
            "name": access.household.name,
            "effective_role": access.effective_role,
            "dietary_preferences": list(access.household.dietary_preferences or []),
        },
        "pantry": {
            "counts": pantry_overview.counts.model_dump(),
            "classified_products": classified_products,
            "fallback_products": fallback_products,
            "stock_lots": [
                {
                    "product_name": lot.product_name,
                    "quantity": str(lot.quantity),
                    "unit": lot.unit,
                    "location_name": lot.location_name,
                    "location_group_name": lot.location_group_name,
                    "expires_on": lot.expires_on,
                    "is_near_expiry": lot.is_near_expiry,
                }
                for lot in pantry_overview.stock_lots[:AI_CONTEXT_MAX_STOCK_LOTS]
            ],
            "near_expiry": [
                {
                    "product_name": lot.product_name,
                    "quantity": str(lot.quantity),
                    "unit": lot.unit,
                    "location_name": lot.location_name,
                    "expires_on": lot.expires_on,
                }
                for lot in near_expiry.lots[:AI_CONTEXT_MAX_NEAR_EXPIRY_LOTS]
            ],
        },
        "recipes": {
            "items": [
                {
                    "external_id": recipe.external_id,
                    "title": recipe.title,
                    "ingredient_count": recipe.ingredient_count,
                    "pantry_coverage": recipe.pantry_coverage.model_dump(mode="json"),
                    "updated_at": recipe.updated_at,
                }
                for recipe in recipe_list.recipes[:AI_CONTEXT_MAX_RECIPES]
            ],
            "focused_recipe": _serialize_focused_recipe(recipe_detail) if recipe_detail is not None else None,
        },
        "dietary_context": {
            "household_preferences": list(access.household.dietary_preferences or []),
            "classified_product_count": len(classified_products),
            "fallback_product_count": len(fallback_products),
        },
    }

    return AIContextBundle(
        payload=payload,
        snapshot=AISuggestionContextSnapshot(
            pantry_product_count=pantry_overview.counts.product_count,
            active_lot_count=pantry_overview.counts.active_lot_count,
            near_expiry_lot_count=pantry_overview.counts.near_expiry_lot_count,
            recipe_count=len(recipe_list.recipes),
            recipe_external_id=recipe_detail.external_id if recipe_detail is not None else None,
            recipe_title=recipe_detail.title if recipe_detail is not None else None,
        ),
        diagnostics={
            "applied_optimizations": [
                "compact_focused_recipe",
                "trimmed_recipe_lists",
                "structured_product_preference",
                "trimmed_fallback_product_notes",
            ],
            "approx_context_tokens": estimate_ai_payload_tokens(payload),
            "classified_product_count_sent": len(classified_products),
            "fallback_product_count_sent": len(fallback_products),
            "recipe_count_sent": min(len(recipe_list.recipes), AI_CONTEXT_MAX_RECIPES),
        },
    )
