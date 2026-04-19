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
from app.services.ai_config import (
    RUNTIME_HEALTH_CACHE_SOURCE_CACHED,
    get_ai_feature_enabled,
    get_runtime_provider_health,
    has_selected_model,
    normalize_provider_model,
    normalize_provider_type,
    provider_is_ready_for_runtime,
    record_provider_runtime_failure,
    resolve_provider_config,
)
from app.services.ai_providers.openai_compat import is_supported_openai_model
from app.services.ai_context import build_household_ai_context
from app.services.platform_features import FLAG_AI_SUGGESTIONS, get_effective_feature_flag, require_feature_enabled
from app.services.ai_prompts import build_suggestion_prompt_plan
from app.services.ai_providers import StructuredCompletionRequest, build_ai_provider_adapter
from app.services.ai_runtime import estimate_ai_payload_tokens, normalize_ai_error, serialize_ai_usage_metrics
from app.services.audit import record_audit_event
from app.services.tenancy import HouseholdAccess
from app.services.usage_counters import check_usage_quota

logger = structlog.get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_household_ai_feature_status(
    db: Session,
    *,
    household: Household,
) -> AIFeatureStatusSummary:
    feature_gate = get_effective_feature_flag(
        db,
        flag_key=FLAG_AI_SUGGESTIONS,
        household=household,
    )
    if not feature_gate.enabled:
        return AIFeatureStatusSummary(
            feature_enabled=False,
            available=False,
            reason="AI suggestions are disabled for this household.",
        )

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
    provider_type = normalize_provider_type(config.provider_type, base_url=config.base_url)
    default_model = normalize_provider_model(provider_type, config.default_model)
    if not config.is_enabled:
        return AIFeatureStatusSummary(
            feature_enabled=True,
            available=False,
            reason="The configured AI provider is currently disabled.",
            provider_type=provider_type,
            default_model=default_model,
            config_external_id=config.external_id,
            health_status=config.health_status,
            health_checked_at=config.health_checked_at,
        )

    runtime_ready, runtime_reason = provider_is_ready_for_runtime(config)
    if not runtime_ready:
        return AIFeatureStatusSummary(
            feature_enabled=True,
            available=False,
            reason=runtime_reason,
            provider_type=provider_type,
            default_model=default_model if has_selected_model(config) else None,
            config_external_id=config.external_id,
            health_status=config.health_status,
            health_checked_at=config.health_checked_at,
        )

    if config.health_status == AI_HEALTH_UNHEALTHY:
        if provider_type == "openai" and is_supported_openai_model(default_model):
            return AIFeatureStatusSummary(
                feature_enabled=True,
                available=True,
                provider_type=provider_type,
                default_model=default_model,
                config_external_id=config.external_id,
                health_status=config.health_status,
                health_checked_at=config.health_checked_at,
            )
        reason = str(
            normalize_ai_error(
                config.health_error or "The configured AI provider is unhealthy.",
                provider_type=provider_type,
                model=default_model,
            )
        )
        return AIFeatureStatusSummary(
            feature_enabled=True,
            available=False,
            reason=reason,
            provider_type=provider_type,
            default_model=default_model,
            config_external_id=config.external_id,
            health_status=config.health_status,
            health_checked_at=config.health_checked_at,
        )

    return AIFeatureStatusSummary(
        feature_enabled=True,
        available=True,
        provider_type=provider_type,
        default_model=default_model,
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

    health_result = get_runtime_provider_health(db, config=resolved.record)
    health = health_result.health
    feature = build_household_ai_feature_status(db, household=access.household)
    if not health.is_healthy or not feature.available:
        raise ValueError(feature.reason or health.message or "The AI provider is unavailable.")

    context_bundle = build_household_ai_context(db, access=access, request=request)
    prompt_plan = build_suggestion_prompt_plan(
        household_name=access.household.name,
        request=request,
        context_payload=context_bundle.payload,
    )
    approx_input_tokens = estimate_ai_payload_tokens(prompt_plan.user_payload)
    adapter = build_ai_provider_adapter(resolved.runtime)

    logger.info(
        "ai.request.started",
        household_external_id=access.household.external_id,
        actor_external_id=actor.external_id,
        provider_config_external_id=resolved.record.external_id,
        provider_type=resolved.record.provider_type,
        model=resolved.record.default_model,
        suggestion_kind=request.kind,
        approx_input_tokens=approx_input_tokens,
        approx_context_tokens=context_bundle.diagnostics["approx_context_tokens"],
        provider_health_source=health_result.source,
        provider_health_cache_age_seconds=health_result.cache_age_seconds,
        used_cached_health_check=health_result.source == RUNTIME_HEALTH_CACHE_SOURCE_CACHED,
        applied_optimizations=context_bundle.diagnostics["applied_optimizations"],
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
            "approx_input_tokens": approx_input_tokens,
            "provider_health_source": health_result.source,
            "provider_health_cache_age_seconds": health_result.cache_age_seconds,
            "context_optimizations": context_bundle.diagnostics["applied_optimizations"],
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
        logger.warning(
            "ai.request.failed",
            household_external_id=access.household.external_id,
            provider_config_external_id=resolved.record.external_id,
            provider_type=resolved.record.provider_type,
            model=resolved.record.default_model,
            suggestion_kind=request.kind,
            error=ai_error.technical_message,
            provider_health_source=health_result.source,
            approx_input_tokens=approx_input_tokens,
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
                "error": ai_error.technical_message,
                "provider_health_source": health_result.source,
                "approx_input_tokens": approx_input_tokens,
            },
        )
        db.commit()
        raise ai_error from exc

    duration_ms = round((perf_counter() - started) * 1000, 2)
    provider_usage = serialize_ai_usage_metrics(completion.usage)
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
        approx_input_tokens=approx_input_tokens,
        provider_usage=provider_usage,
        provider_health_source=health_result.source,
        applied_optimizations=context_bundle.diagnostics["applied_optimizations"],
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
            "approx_input_tokens": approx_input_tokens,
            "provider_usage": provider_usage,
            "provider_health_source": health_result.source,
            "provider_health_cache_age_seconds": health_result.cache_age_seconds,
            "context_optimizations": context_bundle.diagnostics["applied_optimizations"],
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
