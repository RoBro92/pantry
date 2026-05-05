from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db_session
from app.services.runtime_status import check_redis_health

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(request: Request):
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
        "version": settings.app_version,
        "request_id": getattr(request.state, "request_id", None),
    }


def _alembic_head_revision() -> str | None:
    api_root = Path(__file__).resolve().parents[3]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


def _database_readiness(db: Session) -> dict[str, object]:
    db.execute(text("SELECT 1"))
    current_revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    expected_revision = _alembic_head_revision()
    migration_status = "ok" if current_revision == expected_revision else "out_of_date"
    return {
        "database": {"status": "ok"},
        "migrations": {
            "status": migration_status,
            "current_revision": current_revision,
            "expected_revision": expected_revision,
        },
    }


@router.get("/ready")
def readiness(db: Session = Depends(get_db_session)):
    settings = get_settings()
    checks: dict[str, object] = {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
        "version": settings.app_version,
    }

    try:
        checks.update(_database_readiness(db))
    except Exception as exc:
        checks["database"] = {"status": "unavailable", "message": str(exc)}
        checks["migrations"] = {"status": "unknown"}

    redis = check_redis_health()
    checks["redis"] = {
        "status": redis.status,
        "latency_ms": redis.latency_ms,
        "message": redis.message,
    }

    is_ready = (
        checks.get("database", {}).get("status") == "ok"  # type: ignore[union-attr]
        and checks.get("migrations", {}).get("status") == "ok"  # type: ignore[union-attr]
        and redis.status == "ok"
    )
    checks["status"] = "ok" if is_ready else "not_ready"
    return JSONResponse(status_code=200 if is_ready else 503, content=checks)
