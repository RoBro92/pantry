from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from time import perf_counter

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.household import Household
from app.models.import_job import ImportJob
from app.models.product import Product
from app.models.product_intelligence_run import ProductIntelligenceRun
from app.models.recipe import Recipe
from app.models.recipe_url_import import RecipeURLImport
from app.models.stock_lot import StockLot
from app.models.user import User
from app.services.ai_config import get_instance_provider_config, serialize_provider_config
from app.services.import_processing import IMPORT_JOB_RESUME_TIMEOUT
from app.services.instance_settings import build_public_base_url_summary, build_smtp_summary
from app.services.product_intelligence_runs import RUN_RESUME_TIMEOUT
from app.services.recipe_url_imports import RECIPE_URL_IMPORT_RESUME_TIMEOUT
from app.services.releases import build_release_check_summary
from app.services.runtime_status import check_redis_health, read_worker_heartbeat

API_PROCESS_STARTED_AT = datetime.now(timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_bytes(size_bytes: int | None) -> str | None:
    if size_bytes is None:
        return None
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return None


def _database_diagnostics(db: Session) -> dict[str, object]:
    bind = db.get_bind()
    dialect = bind.dialect.name
    started = perf_counter()
    db.execute(text("SELECT 1"))
    latency_ms = round((perf_counter() - started) * 1000, 2)

    name: str | None = None
    size_bytes: int | None = None
    note: str | None = None

    if dialect == "postgresql":
        name = db.scalar(text("SELECT current_database()"))
        size_bytes = db.scalar(text("SELECT pg_database_size(current_database())"))
    elif dialect == "sqlite":
        name = bind.url.database
        page_count = db.scalar(text("PRAGMA page_count"))
        page_size = db.scalar(text("PRAGMA page_size"))
        if page_count is not None and page_size is not None:
            size_bytes = int(page_count) * int(page_size)
    else:
        note = f"Storage size is not implemented for database engine {dialect}."

    return {
        "status": "ok",
        "engine": dialect,
        "latency_ms": latency_ms,
        "database_name": name,
        "size_bytes": size_bytes,
        "size_pretty": _format_bytes(size_bytes),
        "note": note,
    }


def _count_scalar(db: Session, model) -> int:
    return db.scalar(select(func.count(model.id))) or 0


def _status_counts(db: Session, model) -> defaultdict[str, int]:
    counts = defaultdict(int)
    for status, count in db.execute(select(model.status, func.count(model.id)).group_by(model.status)).all():
        counts[status] = count
    return counts


def _import_queue_counts(db: Session, *, now: datetime) -> dict[str, int]:
    counts = _status_counts(db, ImportJob)
    stale_processing = db.scalar(
        select(func.count(ImportJob.id))
        .where(ImportJob.status == "processing")
        .where(
            or_(
                ImportJob.processing_started_at.is_(None),
                ImportJob.processing_started_at < (now - IMPORT_JOB_RESUME_TIMEOUT),
            )
        )
    ) or 0
    return {
        "queued": counts["queued"],
        "processing": counts["processing"],
        "stale_processing": stale_processing,
        "failed": counts["failed"],
        "completed": counts["completed"],
        "confirmed": counts["confirmed"],
    }


def _recipe_url_import_queue_counts(db: Session, *, now: datetime) -> dict[str, int]:
    counts = _status_counts(db, RecipeURLImport)
    stale_processing = db.scalar(
        select(func.count(RecipeURLImport.id))
        .where(RecipeURLImport.status == "processing")
        .where(RecipeURLImport.updated_at < (now - RECIPE_URL_IMPORT_RESUME_TIMEOUT))
    ) or 0
    return {
        "queued": counts["queued"],
        "processing": counts["processing"],
        "stale_processing": stale_processing,
        "imported": counts["imported"],
        "failed": counts["failed"],
    }


def _product_intelligence_queue_counts(db: Session, *, now: datetime) -> dict[str, int]:
    counts = _status_counts(db, ProductIntelligenceRun)
    stale_running = db.scalar(
        select(func.count(ProductIntelligenceRun.id))
        .where(ProductIntelligenceRun.status == "running")
        .where(
            or_(
                ProductIntelligenceRun.last_progress_at.is_(None),
                ProductIntelligenceRun.last_progress_at < (now - RUN_RESUME_TIMEOUT),
            )
        )
    ) or 0
    return {
        "queued": counts["queued"],
        "running": counts["running"],
        "stale_running": stale_running,
        "completed": counts["completed"],
        "partially_completed": counts["partially_completed"],
        "failed": counts["failed"],
    }


def _worker_diagnostics() -> dict[str, object]:
    heartbeat = read_worker_heartbeat()
    if heartbeat is None:
        return {
            "status": "unavailable",
            "service": None,
            "version": None,
            "mode": None,
            "poll_interval_seconds": None,
            "started_at": None,
            "last_seen_at": None,
            "heartbeat_age_seconds": None,
            "message": "No worker heartbeat is currently available.",
        }

    now = _utc_now()
    last_seen_at = heartbeat.get("last_seen_at")
    poll_interval_seconds = heartbeat.get("poll_interval_seconds")
    age_seconds = (
        max(int((now - last_seen_at).total_seconds()), 0)
        if isinstance(last_seen_at, datetime)
        else None
    )
    is_stale = age_seconds is not None and isinstance(poll_interval_seconds, int) and age_seconds > (poll_interval_seconds * 3)

    return {
        "status": "stale" if is_stale else str(heartbeat.get("status") or "ok"),
        "service": heartbeat.get("service"),
        "version": heartbeat.get("version"),
        "mode": heartbeat.get("mode"),
        "poll_interval_seconds": poll_interval_seconds,
        "started_at": heartbeat.get("started_at"),
        "last_seen_at": last_seen_at,
        "heartbeat_age_seconds": age_seconds,
        "message": "Worker heartbeat is stale." if is_stale else None,
    }


def _counts_summary(db: Session) -> dict[str, int]:
    return {
        "households": _count_scalar(db, Household),
        "users": _count_scalar(db, User),
        "products": _count_scalar(db, Product),
        "stock_lots": _count_scalar(db, StockLot),
        "recipes": _count_scalar(db, Recipe),
        "import_jobs": _count_scalar(db, ImportJob),
    }


def _ai_summary(db: Session) -> dict[str, object]:
    config = get_instance_provider_config(db)
    if config is None:
        return {
            "configured": False,
            "provider_type": None,
            "is_enabled": False,
            "health_status": None,
            "default_model": None,
            "last_success_at": None,
        }

    summary = serialize_provider_config(config)
    return {
        "configured": True,
        "provider_type": summary["provider_type"],
        "is_enabled": summary["is_enabled"],
        "health_status": summary["health_status"],
        "default_model": summary["default_model"],
        "last_success_at": summary["last_success_at"],
    }


def build_diagnostics_report(db: Session) -> dict[str, object]:
    settings = get_settings()
    now = _utc_now()
    redis_health = check_redis_health()
    public_base_url = build_public_base_url_summary(db)
    import_queue_counts = _import_queue_counts(db, now=now)
    recipe_url_import_counts = _recipe_url_import_queue_counts(db, now=now)
    product_intelligence_counts = _product_intelligence_queue_counts(db, now=now)

    return {
        "generated_at": now,
        "policy": "real_data_only",
        "app": {
            "service": settings.service_name,
            "environment": settings.environment,
            "version": settings.app_version,
            "deployment_mode": settings.deployment_mode,
            "started_at": API_PROCESS_STARTED_AT,
            "uptime_seconds": max(int((now - API_PROCESS_STARTED_AT).total_seconds()), 0),
        },
        "api": {
            "status": "ok",
            "message": "Diagnostics are being served by the running API process.",
        },
        "worker": _worker_diagnostics(),
        "redis": {
            "status": redis_health.status,
            "latency_ms": redis_health.latency_ms,
            "message": redis_health.message,
        },
        "queue": {
            "backend": "database",
            "queued_import_jobs": import_queue_counts["queued"],
            "processing_import_jobs": import_queue_counts["processing"],
            "stale_processing_import_jobs": import_queue_counts["stale_processing"],
            "failed_import_jobs": import_queue_counts["failed"],
            "completed_import_jobs": import_queue_counts["completed"],
            "confirmed_import_jobs": import_queue_counts["confirmed"],
            "imports": import_queue_counts,
            "recipe_url_imports": recipe_url_import_counts,
            "product_intelligence_runs": product_intelligence_counts,
            "message": "Queue visibility is measured from durable database records. Redis is not the durable queue in this milestone.",
        },
        "database": _database_diagnostics(db),
        "counts": _counts_summary(db),
        "ai_provider": _ai_summary(db),
        "release_check": build_release_check_summary(db),
        "smtp": build_smtp_summary(db),
        "public_base_url": public_base_url,
        "limitations": [
            "CPU, memory, filesystem, and host/container metrics are intentionally unavailable because the application does not directly observe them.",
            "Worker health is based on a Redis heartbeat published by the worker process; when no heartbeat is present the status is reported as unavailable rather than inferred.",
        ],
    }
