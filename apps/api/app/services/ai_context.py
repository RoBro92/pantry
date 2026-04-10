from __future__ import annotations

from dataclasses import dataclass

from app.schemas.ai import AISuggestionContextSnapshot, AISuggestionRequest
from app.services.pantry_queries import PantryFilterOptions, build_near_expiry_response, build_pantry_overview
from app.services.recipe_queries import build_recipe_detail_response, build_recipe_list_response
from app.services.tenancy import HouseholdAccess


@dataclass(frozen=True)
class AIContextBundle:
    payload: dict[str, object]
    snapshot: AISuggestionContextSnapshot


def _trim_text(value: str | None, *, limit: int) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped[:limit]


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

    for product in pantry_overview.products[:24]:
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
            classified_products.append(
                {
                    **base_product,
                    "food_category": product.intelligence.food_category,
                    "primary_ingredient_type": product.intelligence.primary_ingredient_type,
                    "ingredient_families": product.intelligence.ingredient_families,
                    "dietary_tags": product.intelligence.dietary_tags,
                    "allergen_tags": product.intelligence.allergen_tags,
                    "recipe_role_tags": product.intelligence.recipe_role_tags,
                    "substitution_groups": product.intelligence.substitution_groups,
                    "pantry_use_tags": product.intelligence.pantry_use_tags,
                    "structured_metadata": product.intelligence.structured_metadata.model_dump(mode="json"),
                    "is_stale": product.intelligence.is_stale,
                }
            )
        else:
            fallback_products.append(
                {
                    **base_product,
                    "manual_ingredient_tags": product.manual_ingredient_tags[:8],
                    "aliases": product.aliases[:6],
                    "notes": _trim_text(product.notes, limit=180),
                    "enrichment": (
                        {
                            "ingredient_tags": product.enrichment.ingredient_tags[:10],
                            "dietary_tags": product.enrichment.dietary_tags[:8],
                            "allergen_tags": product.enrichment.allergen_tags[:8],
                            "categories": product.enrichment.categories[:8],
                        }
                        if product.enrichment is not None
                        else None
                    ),
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
                for lot in pantry_overview.stock_lots[:20]
            ],
            "near_expiry": [
                {
                    "product_name": lot.product_name,
                    "quantity": str(lot.quantity),
                    "unit": lot.unit,
                    "location_name": lot.location_name,
                    "expires_on": lot.expires_on,
                }
                for lot in near_expiry.lots[:10]
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
                for recipe in recipe_list.recipes[:10]
            ],
            "focused_recipe": recipe_detail.model_dump(mode="json") if recipe_detail is not None else None,
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
    )
