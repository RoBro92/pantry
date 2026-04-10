from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.membership import Membership
from app.schemas.ai import (
    AIHouseholdMemberSummary,
    AIMealPlannerPantrySummary,
    AIMealPlannerResponse,
    AIMealSuggestionContextSnapshot,
    AIMealSuggestionRequest,
)
from app.services.ai_suggestions import build_household_ai_feature_status
from app.services.pantry_queries import PantryFilterOptions, build_near_expiry_response, build_pantry_overview
from app.services.recipe_queries import build_recipe_list_response
from app.services.recipe_suggestion_providers import list_recipe_suggestion_candidates
from app.services.tenancy import HouseholdAccess

DIETARY_NONE_OPTION = "None"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw_value in values:
        value = raw_value.strip()
        if not value:
            continue
        if value.casefold() == DIETARY_NONE_OPTION.casefold():
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _serialize_enrichment(enrichment) -> dict[str, object] | None:
    if enrichment is None:
        return None
    return {
        "ingredient_tags": list(enrichment.ingredient_tags or [])[:8],
        "ingredients_text": (enrichment.ingredients_text or "")[:180] or None,
        "allergen_tags": list(enrichment.allergen_tags or [])[:8],
        "allergens_text": (enrichment.allergens_text or "")[:120] or None,
        "labels": list(enrichment.labels or [])[:8],
        "dietary_tags": list(enrichment.dietary_tags or [])[:8],
        "nutrition_summary_text": enrichment.nutrition_summary_text,
    }


def _load_household_members(db: Session, *, access: HouseholdAccess) -> list[AIHouseholdMemberSummary]:
    memberships = db.scalars(
        select(Membership)
        .where(Membership.household_id == access.household.id)
        .where(Membership.is_active.is_(True))
        .options(selectinload(Membership.user))
        .order_by(Membership.created_at.asc())
    ).all()
    members: list[AIHouseholdMemberSummary] = []
    for membership in memberships:
        user = membership.user
        if user is None or not user.is_active:
            continue
        members.append(
            AIHouseholdMemberSummary(
                user_external_id=user.external_id,
                display_name=user.display_name or user.email,
                dietary_preferences=_dedupe(list(user.dietary_preferences or [])),
            )
        )
    return members


def _resolve_selected_members(
    members: list[AIHouseholdMemberSummary],
    *,
    selected_user_external_ids: list[str],
) -> list[AIHouseholdMemberSummary]:
    if not selected_user_external_ids:
        return []
    member_map = {member.user_external_id: member for member in members}
    missing = [user_external_id for user_external_id in selected_user_external_ids if user_external_id not in member_map]
    if missing:
        raise ValueError("One or more selected users are not part of this household.")
    return [member_map[user_external_id] for user_external_id in selected_user_external_ids]


def _resolve_effective_preferences(
    *,
    household_preferences: list[str],
    selected_members: list[AIHouseholdMemberSummary],
    request: AIMealSuggestionRequest,
) -> dict[str, list[str]]:
    base_preferences = _dedupe(
        household_preferences
        + [preference for member in selected_members for preference in member.dietary_preferences]
    )
    removed = {value.casefold() for value in _dedupe(request.removed_preference_pills)}
    active_preferences = [
        value for value in base_preferences if value.casefold() not in removed
    ]
    active_preferences = _dedupe(active_preferences + _dedupe(request.temporary_include_preferences))
    excluded_preferences = _dedupe(request.temporary_exclude_preferences)
    return {
        "base_preferences": base_preferences,
        "active_preferences": active_preferences,
        "excluded_preferences": excluded_preferences,
        "removed_preferences": _dedupe(request.removed_preference_pills),
    }


@dataclass(frozen=True)
class AIMealContextBundle:
    payload: dict[str, object]
    snapshot: AIMealSuggestionContextSnapshot
    selected_members: list[AIHouseholdMemberSummary]
    effective_preferences: list[str]


def build_meal_planner_response(
    db: Session,
    *,
    access: HouseholdAccess,
) -> AIMealPlannerResponse:
    feature = build_household_ai_feature_status(db, household=access.household)
    pantry_overview = build_pantry_overview(
        db,
        access=access,
        filters=PantryFilterOptions(),
        page=1,
        page_size=50,
    )
    recipe_list = build_recipe_list_response(db, access=access)
    members = _load_household_members(db, access=access)
    near_expiry_product_names = _dedupe(
        [lot.product_name for lot in pantry_overview.stock_lots if lot.is_near_expiry]
    )
    return AIMealPlannerResponse(
        household_external_id=access.household.external_id,
        household_name=access.household.name,
        feature=feature,
        household_dietary_preferences=_dedupe(list(access.household.dietary_preferences or [])),
        members=members,
        pantry_summary=AIMealPlannerPantrySummary(
            pantry_product_count=pantry_overview.counts.product_count,
            active_lot_count=pantry_overview.counts.active_lot_count,
            near_expiry_lot_count=pantry_overview.counts.near_expiry_lot_count,
            near_expiry_product_names=near_expiry_product_names[:8],
            local_recipe_count=len(recipe_list.recipes),
        ),
    )


def build_ai_meal_context(
    db: Session,
    *,
    access: HouseholdAccess,
    request: AIMealSuggestionRequest,
) -> AIMealContextBundle:
    pantry_overview = build_pantry_overview(
        db,
        access=access,
        filters=PantryFilterOptions(),
        page=1,
        page_size=50,
    )
    near_expiry = build_near_expiry_response(db, access=access, days=7)
    members = _load_household_members(db, access=access)
    selected_members = _resolve_selected_members(
        members,
        selected_user_external_ids=request.selected_user_external_ids,
    )
    preference_sets = _resolve_effective_preferences(
        household_preferences=_dedupe(list(access.household.dietary_preferences or [])),
        selected_members=selected_members,
        request=request,
    )
    candidate_recipes = list_recipe_suggestion_candidates(db, access=access, limit=8)

    payload = {
        "household": {
            "external_id": access.household.external_id,
            "name": access.household.name,
            "effective_role": access.effective_role,
        },
        "request": {
            "people_count": request.people_count,
            "selected_users": [
                member.model_dump(mode="json") for member in selected_members
            ],
            "meal_type": request.meal_type,
            "extra_portion_count": request.extra_portion_count,
            "max_total_minutes": request.max_total_minutes,
            "prioritize_near_expiry": request.prioritize_near_expiry,
            "allow_extra_ingredients": request.allow_extra_ingredients,
            "pantry_only": request.pantry_only,
        },
        "dietary_preferences": preference_sets,
        "pantry": {
            "counts": pantry_overview.counts.model_dump(),
            "products": [
                {
                    "product_external_id": product.product_external_id,
                    "name": product.product_name,
                    "unit": product.unit,
                    "total_quantity": str(product.total_quantity),
                    "aliases": product.aliases[:6],
                    "manual_ingredient_tags": product.manual_ingredient_tags[:8],
                    "notes": product.notes,
                    "near_expiry_lot_count": product.near_expiry_lot_count,
                    "nearest_expiry_on": product.nearest_expiry_on.isoformat()
                    if product.nearest_expiry_on is not None
                    else None,
                    "locations": [
                        {
                            "location_name": location.location_name,
                            "location_group_name": location.location_group_name,
                            "total_quantity": str(location.total_quantity),
                        }
                        for location in product.locations[:4]
                    ],
                    "enrichment": _serialize_enrichment(product.enrichment),
                }
                for product in pantry_overview.products
            ],
            "near_expiry_lots": [
                {
                    "product_name": lot.product_name,
                    "quantity": str(lot.quantity),
                    "unit": lot.unit,
                    "expires_on": lot.expires_on.isoformat() if lot.expires_on is not None else None,
                    "location_name": lot.location_name,
                    "location_group_name": lot.location_group_name,
                }
                for lot in near_expiry.lots[:16]
            ],
        },
        "recipe_candidates": [
            {
                "provider_name": candidate.provider_name,
                "source_kind": candidate.source_kind,
                "recipe_external_id": candidate.recipe_external_id,
                "title": candidate.title,
                "notes": candidate.notes,
                "source_url": candidate.source_url,
                "pantry_coverage_status": candidate.pantry_coverage_status,
                "shopping_gap_count": candidate.shopping_gap_count,
                "ingredient_count": candidate.ingredient_count,
                "ingredients": [
                    {
                        "name": ingredient.name,
                        "quantity": str(ingredient.quantity),
                        "unit": ingredient.unit,
                        "product_name": ingredient.product.name if ingredient.product is not None else None,
                        "coverage_status": ingredient.coverage.status,
                        "missing_quantity": str(ingredient.coverage.missing_quantity),
                    }
                    for ingredient in candidate.detail.ingredients[:12]
                ],
            }
            for candidate in candidate_recipes
        ],
    }

    return AIMealContextBundle(
        payload=payload,
        snapshot=AIMealSuggestionContextSnapshot(
            pantry_product_count=pantry_overview.counts.product_count,
            active_lot_count=pantry_overview.counts.active_lot_count,
            near_expiry_lot_count=pantry_overview.counts.near_expiry_lot_count,
            selected_user_count=len(selected_members),
            effective_preference_count=len(preference_sets["active_preferences"]) + len(preference_sets["excluded_preferences"]),
            candidate_recipe_count=len(candidate_recipes),
            pantry_only=request.pantry_only,
        ),
        selected_members=selected_members,
        effective_preferences=preference_sets["active_preferences"],
    )
