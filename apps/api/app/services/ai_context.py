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
    enriched_products = [
        {
            "product_external_id": product.product_external_id,
            "product_name": product.product_name,
            "enrichment": product.enrichment.model_dump(mode="json"),
        }
        for product in pantry_overview.products
        if product.enrichment is not None
    ][:20]

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
        },
        "pantry": {
            "counts": pantry_overview.counts.model_dump(),
            "products": [product.model_dump(mode="json") for product in pantry_overview.products[:20]],
            "stock_lots": [lot.model_dump(mode="json") for lot in pantry_overview.stock_lots[:20]],
            "near_expiry": [lot.model_dump(mode="json") for lot in near_expiry.lots[:10]],
        },
        "recipes": {
            "items": [recipe.model_dump(mode="json") for recipe in recipe_list.recipes[:10]],
            "focused_recipe": recipe_detail.model_dump(mode="json") if recipe_detail is not None else None,
        },
        "dietary_context": {
            "enriched_products": enriched_products,
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
