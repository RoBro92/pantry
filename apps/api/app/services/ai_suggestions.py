from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

import structlog
from sqlalchemy.orm import Session

from app.domain.ai import AI_HEALTH_UNHEALTHY
from app.models.household import Household
from app.models.user import User
from app.schemas.ai import (
    AIFeatureStatusSummary,
    AIProviderSuggestionOutput,
    AISuggestionRequest,
    AISuggestionResponse,
)
from app.services.ai_config import get_ai_feature_enabled, refresh_provider_health, resolve_provider_config
from app.services.ai_context import build_household_ai_context
from app.services.ai_prompts import build_suggestion_prompt_plan
from app.services.ai_providers import StructuredCompletionRequest, build_ai_provider_adapter
from app.services.audit import record_audit_event
from app.services.tenancy import HouseholdAccess

logger = structlog.get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_household_ai_feature_status(
    db: Session,
    *,
    household: Household,
) -> AIFeatureStatusSummary:
    if not get_ai_feature_enabled():
        return AIFeatureStatusSummary(
            feature_enabled=False,
            available=False,
            reason="AI features are disabled for this deployment.",
        )

    resolved = resolve_provider_config(db, household=household)
    if resolved is None:
        return AIFeatureStatusSummary(
            feature_enabled=True,
            available=False,
            reason="No AI provider is configured for this installation.",
        )

    config = resolved.record
    if not config.is_enabled:
        return AIFeatureStatusSummary(
            feature_enabled=True,
            available=False,
            reason="The configured AI provider is currently disabled.",
            provider_type=config.provider_type,
            default_model=config.default_model,
            config_external_id=config.external_id,
            health_status=config.health_status,
            health_checked_at=config.health_checked_at,
        )

    if config.health_status == AI_HEALTH_UNHEALTHY:
        return AIFeatureStatusSummary(
            feature_enabled=True,
            available=False,
            reason="The configured AI provider is unhealthy.",
            provider_type=config.provider_type,
            default_model=config.default_model,
            config_external_id=config.external_id,
            health_status=config.health_status,
            health_checked_at=config.health_checked_at,
        )

    return AIFeatureStatusSummary(
        feature_enabled=True,
        available=True,
        provider_type=config.provider_type,
        default_model=config.default_model,
        config_external_id=config.external_id,
        health_status=config.health_status,
        health_checked_at=config.health_checked_at,
    )


def generate_household_ai_suggestions(
    db: Session,
    *,
    access: HouseholdAccess,
    actor: User,
    request: AISuggestionRequest,
) -> AISuggestionResponse:
    feature = build_household_ai_feature_status(db, household=access.household)
    if not feature.feature_enabled:
        raise ValueError(feature.reason or "AI is disabled.")

    resolved = resolve_provider_config(db, household=access.household)
    if resolved is None:
        raise ValueError("No AI provider is configured for this installation.")
    if not resolved.record.is_enabled:
        raise ValueError("The configured AI provider is disabled.")

    health = refresh_provider_health(db, config=resolved.record)
    feature = build_household_ai_feature_status(db, household=access.household)
    if not health.is_healthy or not feature.available:
        raise ValueError(feature.reason or health.message or "The AI provider is unavailable.")

    context_bundle = build_household_ai_context(db, access=access, request=request)
    prompt_plan = build_suggestion_prompt_plan(
        household_name=access.household.name,
        request=request,
        context_payload=context_bundle.payload,
    )
    adapter = build_ai_provider_adapter(resolved.runtime)

    logger.info(
        "ai.request.started",
        household_external_id=access.household.external_id,
        actor_external_id=actor.external_id,
        provider_config_external_id=resolved.record.external_id,
        provider_type=resolved.record.provider_type,
        model=resolved.record.default_model,
        suggestion_kind=request.kind,
    )
    record_audit_event(
        db,
        household=access.household,
        actor=actor,
        action="ai.suggestion.requested",
        target_type="household",
        target_external_id=access.household.external_id,
        event_metadata={
            "provider_config_external_id": resolved.record.external_id,
            "provider_type": resolved.record.provider_type,
            "default_model": resolved.record.default_model,
            "kind": request.kind,
            "recipe_external_id": request.recipe_external_id,
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
        parsed = AIProviderSuggestionOutput.model_validate(completion.parsed_output)
    except Exception as exc:
        logger.exception(
            "ai.request.failed",
            household_external_id=access.household.external_id,
            provider_config_external_id=resolved.record.external_id,
            provider_type=resolved.record.provider_type,
            model=resolved.record.default_model,
            suggestion_kind=request.kind,
        )
        record_audit_event(
            db,
            household=access.household,
            actor=actor,
            action="ai.suggestion.failed",
            target_type="household",
            target_external_id=access.household.external_id,
            event_metadata={
                "provider_config_external_id": resolved.record.external_id,
                "provider_type": resolved.record.provider_type,
                "default_model": resolved.record.default_model,
                "kind": request.kind,
                "error": str(exc),
            },
        )
        db.commit()
        raise

    duration_ms = round((perf_counter() - started) * 1000, 2)
    logger.info(
        "ai.request.completed",
        household_external_id=access.household.external_id,
        provider_config_external_id=resolved.record.external_id,
        provider_type=resolved.record.provider_type,
        model=resolved.record.default_model,
        suggestion_kind=request.kind,
        suggestion_count=len(parsed.suggestions),
        duration_ms=duration_ms,
        provider_request_id=completion.provider_request_id,
    )
    record_audit_event(
        db,
        household=access.household,
        actor=actor,
        action="ai.suggestion.completed",
        target_type="household",
        target_external_id=access.household.external_id,
        event_metadata={
            "provider_config_external_id": resolved.record.external_id,
            "provider_type": resolved.record.provider_type,
            "default_model": resolved.record.default_model,
            "kind": request.kind,
            "suggestion_count": len(parsed.suggestions),
            "duration_ms": duration_ms,
        },
    )
    db.commit()

    return AISuggestionResponse(
        household_external_id=access.household.external_id,
        feature=feature,
        request=request,
        context_snapshot=context_bundle.snapshot,
        suggestions=[
            {
                "title": item.title,
                "summary": item.summary,
                "rationale": item.rationale,
                "pantry_product_names": item.pantry_product_names,
                "expiring_product_names": item.expiring_product_names,
                "missing_product_names": item.missing_product_names,
                "extra_ingredient_names": item.extra_ingredient_names,
                "substitution_ideas": item.substitution_ideas,
                "caution": item.caution,
            }
            for item in parsed.suggestions
        ],
        generated_at=_utc_now(),
    )
