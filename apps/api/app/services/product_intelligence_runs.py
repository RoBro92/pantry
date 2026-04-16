from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import httpx
import structlog
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import SessionLocal
from app.models.base import utc_now
from app.models.household import Household
from app.models.product import Product
from app.models.product_intelligence import ProductIntelligence
from app.models.product_intelligence_run import ProductIntelligenceRun
from app.models.user import User
from app.schemas.pantry import (
    ProductIntelligenceRunEvent,
    ProductIntelligenceRunItem,
    ProductIntelligenceRunRequest,
    ProductIntelligenceRunResponse,
    ProductIntelligenceRunSummary,
)
from app.services.ai_config import refresh_provider_health, resolve_provider_config
from app.services.ai_providers import StructuredCompletionRequest, build_ai_provider_adapter
from app.services.ai_runtime import PantryAIError, normalize_ai_error
from app.services.audit import record_audit_event
from app.services.product_intelligence import (
    PRODUCT_INTELLIGENCE_EXECUTION_AI_GAP_FILL,
    PRODUCT_INTELLIGENCE_EXECUTION_DERIVED_ONLY,
    PRODUCT_INTELLIGENCE_EXECUTION_FULL_AI,
    PRODUCT_INTELLIGENCE_BASE_PROMPT_TOKEN_OVERHEAD,
    PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
    PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
    PRODUCT_INTELLIGENCE_SCOPE,
    PRODUCT_INTELLIGENCE_SOURCE_PROVIDER_DERIVED,
    ProductBatchClassificationOutput,
    ProductClassificationBatchOutput,
    ProductClassificationOutput,
    ProductIntelligenceExecutionPlan,
    ProductIntelligenceStaleness,
    _get_product_by_id,
    _load_household_products,
    _load_target_products,
    apply_product_intelligence_classification,
    build_product_intelligence_execution_plan,
    build_product_classification_batch_schema,
    build_product_intelligence_status,
    estimate_product_intelligence_tokens,
    get_primary_product_intelligence,
    get_product_intelligence_staleness,
    get_product_intelligence_runtime_trim_level,
    merge_gap_fill_product_classification,
    serialize_product_intelligence,
)
from app.services.product_intelligence_profiles import (
    ProductIntelligenceExecutionProfile,
    RetryProfile,
    resolve_product_intelligence_profile,
)

logger = structlog.get_logger(__name__)

RUN_STATUS_QUEUED = "queued"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_PARTIALLY_COMPLETED = "partially_completed"

RUN_TERMINAL_STATUSES = {RUN_STATUS_COMPLETED, RUN_STATUS_FAILED, RUN_STATUS_PARTIALLY_COMPLETED}
RUN_PROGRESS_ITEM_STATUSES = {"classified", "reclassified", "skipped", "failed"}
RUN_RESUME_TIMEOUT = timedelta(minutes=5)
RUN_EVENT_LIMIT = 24


@dataclass(frozen=True)
class PreparedClassificationCandidate:
    product: Product
    payload: dict[str, object]
    approx_input_tokens: int
    staleness: ProductIntelligenceStaleness
    existing_intelligence: ProductIntelligence | None
    execution_strategy: str = PRODUCT_INTELLIGENCE_EXECUTION_FULL_AI
    derived_output: ProductClassificationOutput | None = None


class TransientProviderError(RuntimeError):
    pass


def queue_product_intelligence_run(
    db: Session,
    *,
    household: Household,
    actor: User,
    request: ProductIntelligenceRunRequest,
) -> ProductIntelligenceRunResponse:
    status = build_product_intelligence_status(db, household=household)
    if not status.available:
        raise ValueError(status.reason or "AI product intelligence is unavailable.")

    existing = _load_active_run(db, household=household)
    if existing is not None:
        return ProductIntelligenceRunResponse.model_validate(
            {
                **serialize_product_intelligence_run(existing).model_dump(mode="python"),
                "created": False,
            }
        )

    resolved = resolve_provider_config(db, household=household)
    if resolved is None:
        raise ValueError("No AI provider is configured for this installation.")

    health = refresh_provider_health(db, config=resolved.record)
    if not health.is_healthy:
        raise ValueError(health.message or "The AI provider is unavailable.")

    products = _load_target_products(db, household=household, request=request)
    run = ProductIntelligenceRun(
        household_id=household.id,
        requested_by_user_id=actor.id,
        provider_type=resolved.record.provider_type,
        source_model=resolved.record.default_model,
        mode=request.mode,
        status=RUN_STATUS_QUEUED,
        target_product_external_ids=[product.external_id for product in products],
        target_product_count=len(products),
        items_payload=[],
        events_payload=[],
    )
    db.add(run)
    db.flush()
    _append_run_event(
        run,
        level="info",
        message=f"Queued classification run for {len(products)} product(s).",
    )
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="product.intelligence.run.queued",
        target_type="product_intelligence_run",
        target_external_id=run.external_id,
        event_metadata={
            "mode": request.mode,
            "provider_type": run.provider_type,
            "default_model": run.source_model,
            "total_candidates": len(products),
        },
    )
    db.commit()
    refreshed = _load_run_by_external_id(db, household=household, run_external_id=run.external_id) or run
    return ProductIntelligenceRunResponse.model_validate(
        {
            **serialize_product_intelligence_run(refreshed).model_dump(mode="python"),
            "created": True,
        }
    )


def get_product_intelligence_run_summary(
    db: Session,
    *,
    household: Household,
    run_external_id: str,
) -> ProductIntelligenceRunSummary | None:
    run = _load_run_by_external_id(db, household=household, run_external_id=run_external_id)
    return serialize_product_intelligence_run(run) if run is not None else None


def get_latest_product_intelligence_run_summary(
    db: Session,
    *,
    household: Household,
) -> ProductIntelligenceRunSummary | None:
    run = db.scalar(
        select(ProductIntelligenceRun)
        .where(ProductIntelligenceRun.household_id == household.id)
        .options(selectinload(ProductIntelligenceRun.requested_by_user))
        .order_by(ProductIntelligenceRun.created_at.desc())
    )
    return serialize_product_intelligence_run(run) if run is not None else None


def serialize_product_intelligence_run(run: ProductIntelligenceRun | None) -> ProductIntelligenceRunSummary | None:
    if run is None:
        return None

    requested_by_display = None
    if run.requested_by_user is not None:
        requested_by_display = run.requested_by_user.display_name or run.requested_by_user.email

    return ProductIntelligenceRunSummary(
        external_id=run.external_id,
        mode=run.mode,
        available=True,
        provider_type=run.provider_type,
        default_model=run.source_model,
        classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
        classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
        schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
        status=run.status,
        total_candidates=run.target_product_count,
        processed_count=run.processed_count,
        classified_count=run.classified_count,
        skipped_count=run.skipped_count,
        failed_count=run.failed_count,
        stale_reclassified_count=run.stale_reclassified_count,
        batch_count=run.batch_count,
        completed_batch_count=run.completed_batch_count,
        last_error=run.last_error,
        requested_by_display=requested_by_display,
        items=[ProductIntelligenceRunItem.model_validate(item) for item in (run.items_payload or [])],
        events=[ProductIntelligenceRunEvent.model_validate(item) for item in (run.events_payload or [])],
        created_at=run.created_at,
        started_at=run.processing_started_at,
        last_progress_at=run.last_progress_at,
        completed_at=run.completed_at,
    )


def process_next_product_intelligence_run() -> bool:
    with SessionLocal() as db:
        run = _claim_next_product_intelligence_run(db)
        if run is None:
            return False

        structlog.contextvars.bind_contextvars(
            product_intelligence_run_external_id=run.external_id,
            household_external_id=run.household.external_id,
        )

        try:
            _process_claimed_run(db, run)
        except Exception as exc:
            db.rollback()
            ai_error = normalize_ai_error(
                exc,
                provider_type=run.provider_type,
                model=run.source_model,
            )
            logger.exception("worker.product_intelligence_run.failed", error=ai_error.technical_message)
            run = _load_run_by_id(db, run_id=run.id)
            if run is not None:
                _append_run_event(run, level="error", message=str(ai_error))
                run.last_error = str(ai_error)[:512]
                run.status = (
                    RUN_STATUS_PARTIALLY_COMPLETED if run.processed_count > 0 else RUN_STATUS_FAILED
                )
                run.completed_at = utc_now()
                run.last_progress_at = run.completed_at
                db.add(run)
                record_audit_event(
                    db,
                    household=run.household,
                    actor=run.requested_by_user,
                    action="product.intelligence.run.failed",
                    target_type="product_intelligence_run",
                    target_external_id=run.external_id,
                    event_metadata={
                        "status": run.status,
                        "last_error": run.last_error,
                        "processed_count": run.processed_count,
                        "classified_count": run.classified_count,
                        "failed_count": run.failed_count,
                    },
                )
                db.commit()
        finally:
            structlog.contextvars.unbind_contextvars(
                "product_intelligence_run_external_id",
                "household_external_id",
            )

        return True


def _process_claimed_run(db: Session, run: ProductIntelligenceRun) -> None:
    resolved = resolve_provider_config(db, household=run.household)
    if resolved is None:
        raise ValueError("No AI provider is configured for this installation.")
    if resolved.record.provider_type != run.provider_type:
        raise ValueError("The configured AI provider changed after this run was queued.")

    adapter = build_ai_provider_adapter(resolved.runtime)
    effective_model = run.source_model or resolved.record.default_model
    profile = resolve_product_intelligence_profile(run.provider_type, effective_model)
    all_products = _load_household_products(db, household=run.household)
    products_by_external_id = {product.external_id: product for product in all_products}

    processed_ids = _processed_product_ids(run)
    candidates: list[PreparedClassificationCandidate] = []
    newly_skipped = 0
    newly_derived = 0
    missing_products = 0

    for external_id in run.target_product_external_ids:
        if external_id in processed_ids:
            continue

        product = products_by_external_id.get(external_id)
        if product is None:
            _store_run_item(
                run,
                ProductIntelligenceRunItem(
                    product_external_id=external_id,
                    product_name=external_id,
                    status="failed",
                    message="Product no longer exists.",
                ),
            )
            missing_products += 1
            continue

        intelligence = get_primary_product_intelligence(product)
        staleness = get_product_intelligence_staleness(product, intelligence)
        if run.mode == "unclassified" and intelligence is not None:
            _store_run_item(
                run,
                ProductIntelligenceRunItem(
                    product_external_id=product.external_id,
                    product_name=product.name,
                    status="skipped",
                    message="Product already has product intelligence attached.",
                    stale_before_run=staleness.is_stale,
                    intelligence=serialize_product_intelligence(intelligence, product=product),
                ),
            )
            newly_skipped += 1
            continue

        plan = _fit_batch_plan(
            product,
            profile=profile,
            model=effective_model,
        )
        if plan.strategy == PRODUCT_INTELLIGENCE_EXECUTION_DERIVED_ONLY and plan.derived_output is not None:
            apply_product_intelligence_classification(
                db,
                household=run.household,
                actor=run.requested_by_user,
                product=product,
                parsed=plan.derived_output,
                model=None,
                provider_type=PRODUCT_INTELLIGENCE_SOURCE_PROVIDER_DERIVED,
            )
            db.expire_all()
            refreshed = _get_product_by_id(db, household=run.household, product_id=product.id) or product
            refreshed_intelligence = get_primary_product_intelligence(refreshed)
            _store_run_item(
                run,
                ProductIntelligenceRunItem(
                    product_external_id=refreshed.external_id,
                    product_name=refreshed.name,
                    status="reclassified" if intelligence is not None else "classified",
                    message="Derived product intelligence saved from OFF facts.",
                    confidence=refreshed_intelligence.confidence if refreshed_intelligence is not None else None,
                    stale_before_run=staleness.is_stale,
                    intelligence=serialize_product_intelligence(refreshed_intelligence, product=refreshed),
                ),
            )
            newly_derived += 1
            continue

        candidates.append(
            PreparedClassificationCandidate(
                product=product,
                payload=plan.ai_payload or plan.source_payload,
                approx_input_tokens=estimate_product_intelligence_tokens(plan.ai_payload or plan.source_payload),
                staleness=staleness,
                existing_intelligence=intelligence,
                execution_strategy=plan.strategy,
                derived_output=plan.derived_output,
            )
        )

    if newly_skipped or newly_derived or missing_products:
        message_parts: list[str] = []
        if newly_skipped:
            message_parts.append(f"Skipped {newly_skipped} already-classified product(s).")
        if newly_derived:
            message_parts.append(f"Derived {newly_derived} high-confidence OFF product(s) without AI.")
        if missing_products:
            message_parts.append(f"Marked {missing_products} missing product(s) as failed.")
        _append_run_event(run, level="info", message=" ".join(message_parts))
        _refresh_run_counters(run)
        run.last_progress_at = utc_now()
        db.add(run)
        db.commit()
        run = _load_run_by_id(db, run_id=run.id) or run

    batches = _build_batches(candidates, profile=profile)
    run.batch_count = run.completed_batch_count + len(batches)
    db.add(run)
    db.commit()
    run = _load_run_by_id(db, run_id=run.id) or run

    if not batches:
        _finish_run(db, run, actor=run.requested_by_user)
        return

    consecutive_transient_failures = 0
    pending_candidates = list(candidates)
    batch_index = run.completed_batch_count
    while pending_candidates:
        batch_index += 1
        batch = _build_batches(pending_candidates, profile=profile)[0]
        pending_candidates = pending_candidates[len(batch) :]
        try:
            _process_batch(
                db,
                run=run,
                batch=batch,
                batch_index=batch_index,
                adapter=adapter,
                provider_type=run.provider_type,
                model=effective_model,
                actor=run.requested_by_user,
                profile=profile,
            )
            consecutive_transient_failures = 0
        except TransientProviderError as exc:
            ai_error = normalize_ai_error(
                exc,
                provider_type=run.provider_type,
                model=effective_model,
            )
            consecutive_transient_failures += 1
            _mark_batch_failed(run, batch=batch, batch_index=batch_index, message=str(ai_error))
            _append_run_event(run, level="warning", message=str(ai_error), batch_index=batch_index)
            _refresh_run_counters(run)
            run.last_error = str(ai_error)[:512]
            run.last_progress_at = utc_now()
            db.add(run)
            db.commit()
            run = _load_run_by_id(db, run_id=run.id) or run
            if consecutive_transient_failures >= profile.retry.consecutive_failure_abort_threshold:
                for candidate in pending_candidates:
                    _store_run_item(
                        run,
                        ProductIntelligenceRunItem(
                            product_external_id=candidate.product.external_id,
                            product_name=candidate.product.name,
                            status="failed",
                            message="Run aborted after repeated transient provider failures.",
                            stale_before_run=candidate.staleness.is_stale,
                        ),
                    )
                _append_run_event(
                    run,
                    level="error",
                    message="Stopped after repeated transient provider failures.",
                )
                _refresh_run_counters(run)
                run.last_error = "Stopped after repeated transient provider failures."
                run.last_progress_at = utc_now()
                db.add(run)
                db.commit()
                break
            time.sleep(profile.retry.cooldown_after_exhausted_seconds)
            continue
        except Exception as exc:
            ai_error = normalize_ai_error(
                exc,
                provider_type=run.provider_type,
                model=effective_model,
            )
            _mark_batch_failed(run, batch=batch, batch_index=batch_index, message=str(ai_error))
            _append_run_event(run, level="error", message=str(ai_error), batch_index=batch_index)
            _refresh_run_counters(run)
            run.last_error = str(ai_error)[:512]
            run.last_progress_at = utc_now()
            db.add(run)
            db.commit()
            run = _load_run_by_id(db, run_id=run.id) or run
            continue

        if pending_candidates and profile.pause_between_batches_seconds > 0:
            time.sleep(profile.pause_between_batches_seconds)
        run = _load_run_by_id(db, run_id=run.id) or run

    _finish_run(db, run, actor=run.requested_by_user)


def _process_batch(
    db: Session,
    *,
    run: ProductIntelligenceRun,
    batch: list[PreparedClassificationCandidate],
    batch_index: int,
    adapter,
    provider_type: str,
    model: str,
    actor: User | None,
    profile: ProductIntelligenceExecutionProfile,
) -> None:
    parsed_items = _execute_batch_with_retry(
        adapter=adapter,
        provider_type=provider_type,
        model=model,
        batch=batch,
        batch_index=batch_index,
        profile=profile,
        run=run,
    )
    parsed_by_product_id = {item.product_external_id: item for item in parsed_items}
    for candidate in batch:
        batch_output = parsed_by_product_id.get(candidate.product.external_id)
        if batch_output is None:
            _store_run_item(
                run,
                ProductIntelligenceRunItem(
                    product_external_id=candidate.product.external_id,
                    product_name=candidate.product.name,
                    status="failed",
                    message="Provider response omitted this product.",
                    stale_before_run=candidate.staleness.is_stale,
                    batch_index=batch_index,
                ),
            )
            continue

        parsed = ProductClassificationOutput.model_validate(
            batch_output.model_dump(exclude={"product_external_id"})
        )
        if (
            candidate.execution_strategy == PRODUCT_INTELLIGENCE_EXECUTION_AI_GAP_FILL
            and candidate.derived_output is not None
        ):
            parsed = merge_gap_fill_product_classification(
                parsed,
                derived_output=candidate.derived_output,
            )
        apply_product_intelligence_classification(
            db,
            household=run.household,
            actor=actor or run.requested_by_user,
            product=candidate.product,
            parsed=parsed,
            model=model,
            provider_type=provider_type,
        )
        db.expire_all()
        refreshed = _get_product_by_id(db, household=run.household, product_id=candidate.product.id) or candidate.product
        refreshed_intelligence = get_primary_product_intelligence(refreshed)
        _store_run_item(
            run,
            ProductIntelligenceRunItem(
                product_external_id=refreshed.external_id,
                product_name=refreshed.name,
                status="reclassified" if candidate.existing_intelligence is not None else "classified",
                message="AI product intelligence saved.",
                confidence=refreshed_intelligence.confidence if refreshed_intelligence is not None else None,
                stale_before_run=candidate.staleness.is_stale,
                batch_index=batch_index,
                intelligence=serialize_product_intelligence(refreshed_intelligence, product=refreshed),
            ),
        )

    run.completed_batch_count += 1
    _append_run_event(
        run,
        level="info",
        message=f"Completed batch {batch_index} with {len(batch)} product(s).",
        batch_index=batch_index,
    )
    _refresh_run_counters(run)
    run.last_error = None
    run.last_progress_at = utc_now()
    db.add(run)
    db.commit()


def _execute_batch_with_retry(
    *,
    adapter,
    provider_type: str,
    model: str,
    batch: list[PreparedClassificationCandidate],
    batch_index: int,
    profile: ProductIntelligenceExecutionProfile,
    run: ProductIntelligenceRun,
) -> list[ProductBatchClassificationOutput]:
    attempts = 0
    while True:
        attempts += 1
        try:
            completion = adapter.generate_structured_output(
                StructuredCompletionRequest(
                    model=model,
                    system_prompt=(
                        "You classify pantry products into structured recipe-matching metadata. "
                        "Only use the supplied evidence for each product. "
                        "Each product includes a classification_strategy. "
                        "When classification_strategy is ai_gap_fill, trust derived_facts for factual fields "
                        "such as category, ingredient families, dietary tags, allergen tags, product format, "
                        "and storage profile. Use AI mainly for recipe roles, substitution groups, pantry uses, "
                        "cuisine, flavour, preparation, confidence, and a short rationale. "
                        "Prefer empty values over guesses. "
                        "Keep rationale_short under 160 characters. "
                        "Use concise human-readable tags and categories. "
                        "Return valid JSON only."
                    ),
                    user_payload={
                        "task": "Classify pantry products for recipe matching and pantry suggestions.",
                        "classification_scope": PRODUCT_INTELLIGENCE_SCOPE,
                        "classification_version": PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
                        "schema_version": PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
                        "guidance": {
                            "food_category": "Choose one concise food category per product.",
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
                    "products": [candidate.payload for candidate in batch],
                },
                    output_schema=build_product_classification_batch_schema(),
                    temperature=0.1,
                    max_output_tokens=profile.max_output_tokens,
                    timeout_seconds=profile.request_timeout_seconds,
                )
            )
            parsed = ProductClassificationBatchOutput.model_validate(completion.parsed_output)
            duplicates = {
                item.product_external_id
                for item in parsed.items
                if sum(1 for other in parsed.items if other.product_external_id == item.product_external_id) > 1
            }
            if duplicates:
                raise ValueError("Provider returned duplicate product ids in batch output.")
            return parsed.items
        except Exception as exc:
            if not _is_transient_provider_error(exc):
                raise
            ai_error = normalize_ai_error(
                exc,
                provider_type=provider_type,
                model=model,
            )
            if attempts >= profile.retry.max_attempts:
                raise TransientProviderError(
                    f"Batch {batch_index} failed after {attempts} attempt(s). {ai_error}"
                ) from exc

            delay = _compute_retry_delay(profile.retry, attempt=attempts)
            _append_run_event(
                run,
                level="warning",
                message=(
                    f"Retrying batch {batch_index} after transient provider failure "
                    f"(attempt {attempts + 1} of {profile.retry.max_attempts}) in {delay:.1f}s."
                ),
                batch_index=batch_index,
            )
            time.sleep(delay)


def _build_batches(
    candidates: list[PreparedClassificationCandidate],
    *,
    profile: ProductIntelligenceExecutionProfile,
) -> list[list[PreparedClassificationCandidate]]:
    batches: list[list[PreparedClassificationCandidate]] = []
    current: list[PreparedClassificationCandidate] = []
    current_input_tokens = PRODUCT_INTELLIGENCE_BASE_PROMPT_TOKEN_OVERHEAD
    current_output_tokens = 0
    for candidate in candidates:
        would_exceed_input = current and (
            current_input_tokens + candidate.approx_input_tokens > profile.max_input_tokens
        )
        would_exceed_output = current and (
            current_output_tokens + profile.per_product_output_tokens > profile.max_output_tokens
        )
        would_exceed_count = current and len(current) >= profile.max_products_per_batch
        if would_exceed_input or would_exceed_output or would_exceed_count:
            batches.append(current)
            current = []
            current_input_tokens = PRODUCT_INTELLIGENCE_BASE_PROMPT_TOKEN_OVERHEAD
            current_output_tokens = 0

        current.append(candidate)
        current_input_tokens += candidate.approx_input_tokens
        current_output_tokens += profile.per_product_output_tokens

    if current:
        batches.append(current)
    return batches


def _fit_batch_plan(
    product: Product,
    *,
    profile: ProductIntelligenceExecutionProfile,
    model: str | None,
) -> ProductIntelligenceExecutionPlan:
    trim_level = get_product_intelligence_runtime_trim_level(
        product,
        provider_type=profile.provider_type,
        model=model,
    )
    return build_product_intelligence_execution_plan(
        product,
        provider_type=profile.provider_type,
        model=model,
        trim_level=trim_level,
        include_external_id=True,
    )


def _is_transient_provider_error(exc: Exception) -> bool:
    if isinstance(exc, PantryAIError):
        return exc.retryable
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response is None:
            return True
        return exc.response.status_code in {408, 409, 425, 429, 500, 502, 503, 504}
    message = str(exc).lower()
    return "rate limit" in message or "429" in message or "timed out" in message or "temporarily unavailable" in message


def _compute_retry_delay(retry: RetryProfile, *, attempt: int) -> float:
    raw_delay = min(retry.initial_delay_seconds * (retry.multiplier ** max(attempt - 1, 0)), retry.max_delay_seconds)
    jitter = raw_delay * retry.jitter_ratio
    return max(raw_delay + random.uniform(-jitter, jitter), 0.5)


def _finish_run(db: Session, run: ProductIntelligenceRun, *, actor: User | None) -> None:
    _refresh_run_counters(run)
    run.completed_at = utc_now()
    run.last_progress_at = run.completed_at
    if run.failed_count and (run.classified_count or run.skipped_count):
        run.status = RUN_STATUS_PARTIALLY_COMPLETED
    elif run.failed_count and run.failed_count == run.target_product_count:
        run.status = RUN_STATUS_FAILED
    else:
        run.status = RUN_STATUS_COMPLETED

    _append_run_event(
        run,
        level="info",
        message=(
            f"Run finished with status {run.status}. "
            f"Processed {run.processed_count} of {run.target_product_count} product(s)."
        ),
    )
    db.add(run)
    record_audit_event(
        db,
        household=run.household,
        actor=actor,
        action="product.intelligence.run.completed",
        target_type="product_intelligence_run",
        target_external_id=run.external_id,
        event_metadata={
            "status": run.status,
            "mode": run.mode,
            "provider_type": run.provider_type,
            "default_model": run.source_model,
            "total_candidates": run.target_product_count,
            "processed_count": run.processed_count,
            "classified_count": run.classified_count,
            "skipped_count": run.skipped_count,
            "failed_count": run.failed_count,
            "stale_reclassified_count": run.stale_reclassified_count,
            "batch_count": run.batch_count,
            "completed_batch_count": run.completed_batch_count,
        },
    )
    db.commit()


def _append_run_event(
    run: ProductIntelligenceRun,
    *,
    level: str,
    message: str,
    batch_index: int | None = None,
) -> None:
    events = list(run.events_payload or [])
    events.append(
        ProductIntelligenceRunEvent(
            occurred_at=utc_now(),
            level=level,
            message=message,
            batch_index=batch_index,
        ).model_dump(mode="json")
    )
    run.events_payload = events[-RUN_EVENT_LIMIT:]


def _store_run_item(run: ProductIntelligenceRun, item: ProductIntelligenceRunItem) -> None:
    items = [ProductIntelligenceRunItem.model_validate(payload) for payload in (run.items_payload or [])]
    item_by_external_id = {entry.product_external_id: entry for entry in items}
    item_by_external_id[item.product_external_id] = item
    ordered_items: list[ProductIntelligenceRunItem] = []
    for product_external_id in run.target_product_external_ids:
        current = item_by_external_id.pop(product_external_id, None)
        if current is not None:
            ordered_items.append(current)
    ordered_items.extend(item_by_external_id.values())
    run.items_payload = [entry.model_dump(mode="json") for entry in ordered_items]


def _refresh_run_counters(run: ProductIntelligenceRun) -> None:
    items = [ProductIntelligenceRunItem.model_validate(payload) for payload in (run.items_payload or [])]
    run.processed_count = sum(1 for item in items if item.status in RUN_PROGRESS_ITEM_STATUSES)
    run.classified_count = sum(1 for item in items if item.status in {"classified", "reclassified"})
    run.skipped_count = sum(1 for item in items if item.status == "skipped")
    run.failed_count = sum(1 for item in items if item.status == "failed")
    run.stale_reclassified_count = sum(1 for item in items if item.status == "reclassified" and item.stale_before_run)


def _processed_product_ids(run: ProductIntelligenceRun) -> set[str]:
    return {
        item.product_external_id
        for item in [ProductIntelligenceRunItem.model_validate(payload) for payload in (run.items_payload or [])]
        if item.status in RUN_PROGRESS_ITEM_STATUSES
    }


def _mark_batch_failed(
    run: ProductIntelligenceRun,
    *,
    batch: list[PreparedClassificationCandidate],
    batch_index: int,
    message: str,
) -> None:
    for candidate in batch:
        _store_run_item(
            run,
            ProductIntelligenceRunItem(
                product_external_id=candidate.product.external_id,
                product_name=candidate.product.name,
                status="failed",
                message=message,
                stale_before_run=candidate.staleness.is_stale,
                batch_index=batch_index,
            ),
        )


def _load_active_run(db: Session, *, household: Household) -> ProductIntelligenceRun | None:
    return db.scalar(
        select(ProductIntelligenceRun)
        .where(ProductIntelligenceRun.household_id == household.id)
        .where(ProductIntelligenceRun.status.in_([RUN_STATUS_QUEUED, RUN_STATUS_RUNNING]))
        .options(selectinload(ProductIntelligenceRun.requested_by_user))
        .order_by(ProductIntelligenceRun.created_at.desc())
    )


def _claim_next_product_intelligence_run(db: Session) -> ProductIntelligenceRun | None:
    run = db.scalar(
        select(ProductIntelligenceRun)
        .where(ProductIntelligenceRun.status == RUN_STATUS_QUEUED)
        .options(
            selectinload(ProductIntelligenceRun.household),
            selectinload(ProductIntelligenceRun.requested_by_user),
        )
        .order_by(ProductIntelligenceRun.created_at)
    )
    resumed = False
    if run is None:
        resume_before = utc_now() - RUN_RESUME_TIMEOUT
        run = db.scalar(
            select(ProductIntelligenceRun)
            .where(ProductIntelligenceRun.status == RUN_STATUS_RUNNING)
            .where(
                or_(
                    ProductIntelligenceRun.last_progress_at.is_(None),
                    ProductIntelligenceRun.last_progress_at < resume_before,
                )
            )
            .options(
                selectinload(ProductIntelligenceRun.household),
                selectinload(ProductIntelligenceRun.requested_by_user),
            )
            .order_by(ProductIntelligenceRun.last_progress_at, ProductIntelligenceRun.created_at)
        )
        resumed = run is not None

    if run is None:
        return None

    if run.processing_started_at is None:
        run.processing_started_at = utc_now()
    run.status = RUN_STATUS_RUNNING
    run.last_progress_at = utc_now()
    if resumed:
        _append_run_event(run, level="warning", message="Resuming a stalled background classification run.")
    db.add(run)
    db.commit()
    return _load_run_by_id(db, run_id=run.id)


def _load_run_by_external_id(
    db: Session,
    *,
    household: Household,
    run_external_id: str,
) -> ProductIntelligenceRun | None:
    return db.scalar(
        select(ProductIntelligenceRun)
        .where(ProductIntelligenceRun.household_id == household.id)
        .where(ProductIntelligenceRun.external_id == run_external_id)
        .options(selectinload(ProductIntelligenceRun.requested_by_user))
    )


def _load_run_by_id(db: Session, *, run_id) -> ProductIntelligenceRun | None:
    return db.scalar(
        select(ProductIntelligenceRun)
        .where(ProductIntelligenceRun.id == run_id)
        .options(
            selectinload(ProductIntelligenceRun.household),
            selectinload(ProductIntelligenceRun.requested_by_user),
        )
    )
