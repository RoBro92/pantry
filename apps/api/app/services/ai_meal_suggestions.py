from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from time import perf_counter

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.household import Household
from app.models.location import Location
from app.models.product import Product
from app.models.stock_lot import StockLot
from app.models.user import User
from app.schemas.ai import (
    AIProviderMealSuggestionItem,
    AIProviderMealSuggestionOutput,
    AIMealPlannerResponse,
    AIMealSuggestion,
    AIMealSuggestionContextSnapshot,
    AIMealSuggestionIngredient,
    AIMealSuggestionRequest,
    AIMealSuggestionResponse,
    AIMealSuggestionSourceMetadata,
    CompleteAIMealSuggestionRequest,
    CompleteAIMealSuggestionResponse,
    CompletedAIMealSuggestionIngredient,
)
from app.services.ai_config import (
    provider_is_ready_for_runtime,
    record_provider_runtime_failure,
    refresh_provider_health,
    resolve_provider_config,
)
from app.services.ai_meal_context import build_ai_meal_context, build_meal_planner_response
from app.services.ai_meal_prompts import build_ai_meal_prompt_plan
from app.services.ai_providers import StructuredCompletionRequest, build_ai_provider_adapter
from app.services.ai_runtime import normalize_ai_error
from app.services.ai_suggestions import build_household_ai_feature_status
from app.services.audit import record_audit_event
from app.services.pantry_normalization import lookup_token_overlap, normalize_lookup_name, normalize_unit
from app.services.pantry_stock import remove_stock_from_lot
from app.services.platform_features import FLAG_AI_SUGGESTIONS, require_feature_enabled
from app.services.recipe_matching import resolve_ingredient_product_match
from app.services.tenancy import HouseholdAccess
from app.services.usage_counters import check_usage_quota

logger = structlog.get_logger(__name__)

QUANTITY_STEP = Decimal("0.001")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(QUANTITY_STEP)


def _normalize_unit_soft(value: str) -> str:
    try:
        return normalize_unit(value)
    except ValueError:
        return value.strip().casefold()


def _load_active_lots(
    db: Session,
    *,
    household: Household,
) -> list[StockLot]:
    return db.scalars(
        select(StockLot)
        .where(StockLot.household_id == household.id)
        .where(StockLot.depleted_at.is_(None))
        .where(StockLot.quantity > Decimal("0"))
        .options(
            selectinload(StockLot.product),
            selectinload(StockLot.location).selectinload(Location.location_group),
        )
        .order_by(StockLot.expires_on.asc().nulls_last(), StockLot.created_at.asc())
    ).all()


def _lot_totals_by_product_unit(lots: list[StockLot]) -> dict[tuple[str, str], Decimal]:
    totals: dict[tuple[str, str], Decimal] = {}
    for lot in lots:
        key = (lot.product.external_id, lot.unit)
        totals[key] = _quantize(totals.get(key, Decimal("0.000")) + lot.quantity)
    return totals


def _near_expiry_products(lots: list[StockLot]) -> set[str]:
    threshold = date.today() + timedelta(days=7)
    return {
        lot.product.external_id
        for lot in lots
        if lot.expires_on is not None and lot.expires_on <= threshold
    }


def _match_product(
    db: Session,
    *,
    household: Household,
    ingredient_name: str,
    pantry_product_external_id: str | None,
) -> tuple[Product | None, str | None]:
    if pantry_product_external_id:
        product = db.scalar(
            select(Product)
            .where(Product.household_id == household.id)
            .where(Product.external_id == pantry_product_external_id)
            .options(selectinload(Product.aliases))
        )
        if product is not None and _product_matches_ingredient_name(product, ingredient_name):
            return product, "manual"
    try:
        product, match_source = resolve_ingredient_product_match(
            db,
            household=household,
            ingredient_name=ingredient_name,
            product_external_id=None,
        )
    except ValueError:
        return None, None
    return product, (match_source if product is not None else None)


def _product_matches_ingredient_name(product: Product, ingredient_name: str) -> bool:
    ingredient_lookup = normalize_lookup_name(ingredient_name)
    candidate_names = [product.name, *[alias.name for alias in product.aliases]]
    return any(
        normalize_lookup_name(candidate_name) == ingredient_lookup
        or lookup_token_overlap(candidate_name, ingredient_name) >= 0.5
        for candidate_name in candidate_names
    )


def _build_source_metadata(
    item: AIProviderMealSuggestionItem,
    *,
    recipe_external_ids: set[str],
) -> AIMealSuggestionSourceMetadata:
    source = item.source
    if source.kind == "household_recipe_reference" and source.recipe_external_id not in recipe_external_ids:
        return AIMealSuggestionSourceMetadata(
            kind="ai_generated",
            label="AI-generated suggestion",
        )
    return AIMealSuggestionSourceMetadata(
        kind=source.kind,
        label=source.label,
        recipe_external_id=source.recipe_external_id,
        recipe_title=source.recipe_title,
        recipe_url=source.recipe_url,
        provider_name=source.provider_name,
    )


def _ingredient_display_name(ingredient: AIMealSuggestionIngredient) -> str:
    return f"{ingredient.name} ({ingredient.quantity} {ingredient.unit})"


def _enrich_suggestion(
    db: Session,
    *,
    household: Household,
    item: AIProviderMealSuggestionItem,
    suggestion_id: str,
    active_lots: list[StockLot],
    recipe_external_ids: set[str],
) -> AIMealSuggestion:
    lot_totals = _lot_totals_by_product_unit(active_lots)
    near_expiry_product_ids = _near_expiry_products(active_lots)
    ingredients: list[AIMealSuggestionIngredient] = []

    for index, ingredient in enumerate(item.ingredients, start=1):
        normalized_unit = _normalize_unit_soft(ingredient.unit)
        product, match_source = _match_product(
            db,
            household=household,
            ingredient_name=ingredient.name,
            pantry_product_external_id=ingredient.pantry_product_external_id,
        )
        availability_status = "unmatched"
        pantry_available_quantity = Decimal("0.000")
        covered_quantity = Decimal("0.000")
        missing_quantity = _quantize(ingredient.quantity)
        uses_near_expiry_item = False
        can_consume_from_pantry = False

        if product is not None:
            exact_key = (product.external_id, normalized_unit)
            matched_quantity = lot_totals.get(exact_key, Decimal("0.000"))
            if matched_quantity > Decimal("0.000"):
                pantry_available_quantity = matched_quantity
                covered_quantity = min(matched_quantity, ingredient.quantity)
                missing_quantity = _quantize(ingredient.quantity - covered_quantity)
                availability_status = "available" if missing_quantity == Decimal("0.000") else "partial"
                uses_near_expiry_item = product.external_id in near_expiry_product_ids
                can_consume_from_pantry = True
            else:
                unit_keys = [key for key in lot_totals if key[0] == product.external_id]
                availability_status = "unit_mismatch" if unit_keys else "missing"

        ingredients.append(
            AIMealSuggestionIngredient(
                id=f"{suggestion_id}-ingredient-{index}",
                name=ingredient.name,
                quantity=_quantize(ingredient.quantity),
                unit=normalized_unit,
                note=ingredient.note,
                pantry_product_external_id=product.external_id if product is not None else None,
                pantry_product_name=product.name if product is not None else None,
                pantry_match_source=match_source,
                availability_status=availability_status,
                pantry_available_quantity=_quantize(pantry_available_quantity),
                covered_quantity=_quantize(covered_quantity),
                missing_quantity=_quantize(missing_quantity),
                uses_near_expiry_item=uses_near_expiry_item,
                is_extra_ingredient=ingredient.is_extra_ingredient or availability_status in {"missing", "unmatched", "unit_mismatch"},
                can_consume_from_pantry=can_consume_from_pantry,
            )
        )

    pantry_ingredients_available = [
        ingredient.name
        for ingredient in ingredients
        if ingredient.covered_quantity > Decimal("0.000")
    ]
    extra_ingredients_needed = [
        ingredient.name
        for ingredient in ingredients
        if ingredient.is_extra_ingredient or ingredient.availability_status in {"missing", "unmatched", "unit_mismatch"}
    ]
    near_expiry_names = [
        ingredient.pantry_product_name or ingredient.name
        for ingredient in ingredients
        if ingredient.uses_near_expiry_item
    ]
    near_expiry_note = (
        f"Uses near-expiry pantry items: {', '.join(dict.fromkeys(near_expiry_names))}."
        if near_expiry_names
        else None
    )

    return AIMealSuggestion(
        id=suggestion_id,
        title=item.title,
        short_summary=item.short_summary,
        why_it_matches=item.why_it_matches,
        total_time_minutes=item.total_time_minutes,
        pantry_ingredients_available=list(dict.fromkeys(pantry_ingredients_available)),
        extra_ingredients_needed=list(dict.fromkeys(extra_ingredients_needed)),
        dietary_fit_summary=item.dietary_fit_summary,
        near_expiry_note=near_expiry_note,
        source=_build_source_metadata(item, recipe_external_ids=recipe_external_ids),
        ingredients=ingredients,
        steps=[step.strip() for step in item.steps if step.strip()][:10],
    )


def get_ai_meal_planner(
    db: Session,
    *,
    access: HouseholdAccess,
) -> AIMealPlannerResponse:
    return build_meal_planner_response(db, access=access)


def generate_ai_meal_suggestions(
    db: Session,
    *,
    access: HouseholdAccess,
    actor: User,
    request: AIMealSuggestionRequest,
) -> AIMealSuggestionResponse:
    require_feature_enabled(
        db,
        flag_key=FLAG_AI_SUGGESTIONS,
        household=access.household,
        disabled_message="AI suggestions are disabled for this household.",
    )
    feature = build_household_ai_feature_status(db, household=access.household)
    if not feature.feature_enabled:
        raise ValueError(feature.reason or "AI is disabled.")

    check_usage_quota(
        db,
        counter_key="ai_suggestions",
        scope_type="household",
        scope_key=access.household.external_id,
    )

    resolved = resolve_provider_config(db, household=access.household)
    if resolved is None:
        raise ValueError("No AI provider is configured for this installation.")
    if not resolved.record.is_enabled:
        raise ValueError("The configured AI provider is disabled.")
    runtime_ready, runtime_reason = provider_is_ready_for_runtime(resolved.record)
    if not runtime_ready:
        raise ValueError(runtime_reason or "The AI provider configuration is incomplete.")

    health = refresh_provider_health(db, config=resolved.record)
    feature = build_household_ai_feature_status(db, household=access.household)
    if not health.is_healthy or not feature.available:
        raise ValueError(feature.reason or health.message or "The AI provider is unavailable.")

    context_bundle = build_ai_meal_context(db, access=access, request=request)
    if request.selected_user_external_ids and not context_bundle.selected_members:
        raise ValueError("Select at least one household member for meal suggestions.")

    prompt_plan = build_ai_meal_prompt_plan(
        household_name=access.household.name,
        request=request,
        context_payload=context_bundle.payload,
    )
    adapter = build_ai_provider_adapter(resolved.runtime)

    logger.info(
        "ai.meal_suggestion.request.started",
        household_external_id=access.household.external_id,
        actor_external_id=actor.external_id,
        provider_config_external_id=resolved.record.external_id,
        provider_type=resolved.record.provider_type,
        model=resolved.record.default_model,
        pantry_only=request.pantry_only,
        meal_type=request.meal_type,
    )
    record_audit_event(
        db,
        household=access.household,
        actor=actor,
        action="ai.meal_suggestion.requested",
        target_type="household",
        target_external_id=access.household.external_id,
        event_metadata={
            "provider_config_external_id": resolved.record.external_id,
            "provider_type": resolved.record.provider_type,
            "default_model": resolved.record.default_model,
            "meal_type": request.meal_type,
            "people_count": request.people_count,
            "extra_portion_count": request.extra_portion_count,
            "pantry_only": request.pantry_only,
            "allow_extra_ingredients": request.allow_extra_ingredients,
            "selected_user_external_ids": request.selected_user_external_ids,
        },
    )
    db.commit()

    started = perf_counter()
    try:
        completion = adapter.generate_structured_output(
            StructuredCompletionRequest(
                model=resolved.record.default_model,
                system_prompt=prompt_plan.system_prompt,
                user_payload=prompt_plan.user_payload,
                output_schema=prompt_plan.output_schema,
            )
        )
        parsed = AIProviderMealSuggestionOutput.model_validate(completion.parsed_output)
    except Exception as exc:
        ai_error = normalize_ai_error(
            exc,
            provider_type=resolved.record.provider_type,
            model=resolved.record.default_model,
        )
        record_provider_runtime_failure(
            db,
            config=resolved.record,
            error_message=str(ai_error),
        )
        logger.exception(
            "ai.meal_suggestion.request.failed",
            household_external_id=access.household.external_id,
            provider_config_external_id=resolved.record.external_id,
            provider_type=resolved.record.provider_type,
            model=resolved.record.default_model,
            error=ai_error.technical_message,
        )
        record_audit_event(
            db,
            household=access.household,
            actor=actor,
            action="ai.meal_suggestion.failed",
            target_type="household",
            target_external_id=access.household.external_id,
            event_metadata={
                "provider_config_external_id": resolved.record.external_id,
                "provider_type": resolved.record.provider_type,
                "default_model": resolved.record.default_model,
                "error": ai_error.technical_message,
            },
        )
        db.commit()
        raise ai_error from exc

    active_lots = _load_active_lots(db, household=access.household)
    recipe_external_ids = {
        str(candidate["recipe_external_id"])
        for candidate in context_bundle.payload["recipe_candidates"]  # type: ignore[index]
        if isinstance(candidate, dict) and candidate.get("recipe_external_id")
    }
    suggestions = [
        _enrich_suggestion(
            db,
            household=access.household,
            item=item,
            suggestion_id=f"meal-suggestion-{index}",
            active_lots=active_lots,
            recipe_external_ids=recipe_external_ids,
        )
        for index, item in enumerate(parsed.suggestions[:3], start=1)
    ]

    duration_ms = round((perf_counter() - started) * 1000, 2)
    logger.info(
        "ai.meal_suggestion.request.completed",
        household_external_id=access.household.external_id,
        provider_config_external_id=resolved.record.external_id,
        provider_type=resolved.record.provider_type,
        model=resolved.record.default_model,
        suggestion_count=len(suggestions),
        duration_ms=duration_ms,
        provider_request_id=completion.provider_request_id,
    )
    record_audit_event(
        db,
        household=access.household,
        actor=actor,
        action="ai.meal_suggestion.completed",
        target_type="household",
        target_external_id=access.household.external_id,
        event_metadata={
            "provider_config_external_id": resolved.record.external_id,
            "provider_type": resolved.record.provider_type,
            "default_model": resolved.record.default_model,
            "suggestion_count": len(suggestions),
            "duration_ms": duration_ms,
        },
    )
    db.commit()

    return AIMealSuggestionResponse(
        household_external_id=access.household.external_id,
        feature=feature,
        request=request,
        context_snapshot=AIMealSuggestionContextSnapshot.model_validate(context_bundle.snapshot),
        suggestions=suggestions,
        generated_at=_utc_now(),
    )


def complete_ai_meal_suggestion(
    db: Session,
    *,
    access: HouseholdAccess,
    actor: User,
    request: CompleteAIMealSuggestionRequest,
) -> CompleteAIMealSuggestionResponse:
    active_lots = _load_active_lots(db, household=access.household)
    lots_by_product_unit: dict[tuple[str, str], list[StockLot]] = {}
    for lot in active_lots:
        lots_by_product_unit.setdefault((lot.product.external_id, lot.unit), []).append(lot)

    consumed_ingredients: list[CompletedAIMealSuggestionIngredient] = []
    warnings: list[str] = []

    for ingredient in request.ingredients:
        normalized_unit = _normalize_unit_soft(ingredient.unit)
        requested_quantity = _quantize(ingredient.consume_quantity)
        if ingredient.pantry_product_external_id is None or requested_quantity <= Decimal("0.000"):
            consumed_ingredients.append(
                CompletedAIMealSuggestionIngredient(
                    ingredient_id=ingredient.ingredient_id,
                    name=ingredient.name,
                    unit=normalized_unit,
                    requested_quantity=_quantize(ingredient.quantity),
                    consumed_quantity=Decimal("0.000"),
                    pantry_product_external_id=ingredient.pantry_product_external_id,
                    pantry_product_name=None,
                    status="skipped",
                    note="No pantry deduction selected for this ingredient.",
                )
            )
            continue

        key = (ingredient.pantry_product_external_id, normalized_unit)
        candidate_lots = lots_by_product_unit.get(key, [])
        if not candidate_lots:
            consumed_ingredients.append(
                CompletedAIMealSuggestionIngredient(
                    ingredient_id=ingredient.ingredient_id,
                    name=ingredient.name,
                    unit=normalized_unit,
                    requested_quantity=_quantize(ingredient.quantity),
                    consumed_quantity=Decimal("0.000"),
                    pantry_product_external_id=ingredient.pantry_product_external_id,
                    pantry_product_name=None,
                    status="missing",
                    note="No matching pantry stock was available at completion time.",
                )
            )
            warnings.append(f"{ingredient.name} was not deducted because matching pantry stock was unavailable.")
            continue

        remaining_to_consume = requested_quantity
        consumed_quantity = Decimal("0.000")
        pantry_product_name = candidate_lots[0].product.name

        for lot in candidate_lots:
            if remaining_to_consume <= Decimal("0.000"):
                break
            lot_available = _quantize(lot.quantity)
            if lot_available <= Decimal("0.000"):
                continue
            deduction = min(lot_available, remaining_to_consume)
            remove_stock_from_lot(
                db,
                household=access.household,
                actor=actor,
                lot_external_id=lot.external_id,
                quantity=deduction,
                commit=False,
            )
            remaining_to_consume = _quantize(remaining_to_consume - deduction)
            consumed_quantity = _quantize(consumed_quantity + deduction)

        if consumed_quantity == Decimal("0.000"):
            status = "missing"
            note = "No matching pantry stock could be deducted."
        elif consumed_quantity == requested_quantity:
            status = "consumed"
            note = "Pantry stock deducted."
        else:
            status = "partially_consumed"
            note = "Only the remaining pantry stock could be deducted."
            warnings.append(
                f"{ingredient.name} only had {consumed_quantity} {normalized_unit} available to deduct."
            )

        consumed_ingredients.append(
            CompletedAIMealSuggestionIngredient(
                ingredient_id=ingredient.ingredient_id,
                name=ingredient.name,
                unit=normalized_unit,
                requested_quantity=_quantize(ingredient.quantity),
                consumed_quantity=consumed_quantity,
                pantry_product_external_id=ingredient.pantry_product_external_id,
                pantry_product_name=pantry_product_name,
                status=status,
                note=note,
            )
        )

    any_consumed = any(item.consumed_quantity > Decimal("0.000") for item in consumed_ingredients)
    record_audit_event(
        db,
        household=access.household,
        actor=actor,
        action="ai.meal_suggestion.recipe_completed",
        target_type="household",
        target_external_id=access.household.external_id,
        event_metadata={
            "suggestion_id": request.suggestion_id,
            "suggestion_title": request.suggestion_title,
            "consumed_ingredient_count": sum(
                1 for item in consumed_ingredients if item.consumed_quantity > Decimal("0.000")
            ),
            "warning_count": len(warnings),
        },
    )
    db.commit()

    return CompleteAIMealSuggestionResponse(
        completed=any_consumed,
        suggestion_id=request.suggestion_id,
        suggestion_title=request.suggestion_title,
        consumed_ingredients=consumed_ingredients,
        warnings=warnings,
    )
