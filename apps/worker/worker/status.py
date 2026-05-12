from time import perf_counter

from sqlalchemy import text
from redis.exceptions import RedisError

from app.core.db import SessionLocal
from app.services.runtime_status import check_redis_health
from worker.core.config import WorkerSettings


def _database_status() -> dict[str, object]:
    started = perf_counter()
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as exc:
        return {"status": "unavailable", "latency_ms": None, "message": str(exc)}
    return {
        "status": "ok",
        "latency_ms": round((perf_counter() - started) * 1000, 2),
        "message": None,
    }


def _redis_status() -> dict[str, object]:
    try:
        snapshot = check_redis_health()
    except RedisError as exc:
        return {"status": "unavailable", "latency_ms": None, "message": str(exc)}
    except Exception as exc:
        return {"status": "unavailable", "latency_ms": None, "message": str(exc)}
    return {
        "status": snapshot.status,
        "latency_ms": snapshot.latency_ms,
        "message": snapshot.message,
    }


def _job_loop_status() -> dict[str, object]:
    try:
        from app.services.import_processing import process_next_import_job
        from app.services.product_intelligence_runs import process_next_product_intelligence_run
        from app.services.recipe_url_imports import process_next_recipe_url_import
    except Exception as exc:
        return {"status": "unavailable", "queues": [], "message": str(exc)}

    processors = {
        "imports": process_next_import_job,
        "recipe_url_imports": process_next_recipe_url_import,
        "product_intelligence_runs": process_next_product_intelligence_run,
    }
    unavailable = [name for name, processor in processors.items() if not callable(processor)]
    return {
        "status": "unavailable" if unavailable else "ok",
        "queues": list(processors),
        "message": f"Queue processors are not callable: {', '.join(unavailable)}." if unavailable else None,
    }


def build_status_snapshot(settings: WorkerSettings) -> dict[str, object]:
    database = _database_status()
    redis = _redis_status()
    job_loop = _job_loop_status()
    overall_status = "ok" if all(
        check["status"] == "ok" for check in (database, redis, job_loop)
    ) else "degraded"
    return {
        "status": overall_status,
        "service": settings.service_name,
        "environment": settings.environment,
        "version": settings.app_version,
        "mode": "import-poller",
        "poll_interval_seconds": settings.poll_interval_seconds,
        "checks": {
            "database": database,
            "redis": redis,
            "job_loop": job_loop,
        },
    }
