from __future__ import annotations

import structlog
from sqlalchemy.orm import Session

from app.models.ai_provider_config import AIProviderConfig
from app.models.user import User
from app.services.ai_config import refresh_provider_health
from app.services.instance_settings import record_smtp_test_result
from app.services.smtp import run_smtp_connectivity_test

logger = structlog.get_logger(__name__)


def run_instance_ai_health_check(db: Session, *, config: AIProviderConfig) -> None:
    try:
        health = refresh_provider_health(db, config=config)
    except Exception as exc:
        logger.warning(
            "instance_integration_checks.ai_health_check_failed",
            provider_type=config.provider_type,
            default_model=config.default_model,
            error=str(exc),
        )
        return

    if not health.is_healthy:
        logger.warning(
            "instance_integration_checks.ai_provider_unhealthy",
            provider_type=config.provider_type,
            default_model=config.default_model,
            error=health.message,
        )


def run_instance_smtp_health_check(db: Session, *, actor: User) -> None:
    try:
        result = run_smtp_connectivity_test(db)
        record_smtp_test_result(
            db,
            actor=actor,
            status=result.status,
            error=None if result.ok else result.message,
        )
        if not result.ok:
            logger.warning(
                "instance_integration_checks.smtp_connectivity_failed",
                error=result.message,
            )
    except Exception as exc:
        record_smtp_test_result(
            db,
            actor=actor,
            status="failed",
            error=str(exc),
        )
        logger.warning(
            "instance_integration_checks.smtp_health_check_failed",
            error=str(exc),
        )
