from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_platform_admin
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.ai import (
    AIProviderConfigResponse,
    AIProviderConfigSummary,
    AIProviderConfigUpsertRequest,
    AIProviderHealthResponse,
    AIProviderHealthSummary,
)
from app.services.ai_config import (
    get_ai_feature_enabled,
    get_instance_provider_config,
    refresh_provider_health,
    serialize_provider_config,
    upsert_instance_provider_config,
)

router = APIRouter(prefix="/platform-admin/ai", tags=["platform-admin-ai"])


def _config_summary_or_none(config) -> AIProviderConfigSummary | None:
    payload = serialize_provider_config(config)
    return AIProviderConfigSummary.model_validate(payload) if payload is not None else None


@router.get("/provider-config", response_model=AIProviderConfigResponse)
def get_provider_config(
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    return AIProviderConfigResponse(
        feature_enabled=get_ai_feature_enabled(),
        config=_config_summary_or_none(get_instance_provider_config(db)),
    )


@router.put("/provider-config", response_model=AIProviderConfigResponse)
def put_provider_config(
    payload: AIProviderConfigUpsertRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_platform_admin),
):
    try:
        config = upsert_instance_provider_config(
            db,
            actor=current_user,
            provider_type=payload.provider_type,
            base_url=payload.base_url,
            default_model=payload.default_model,
            api_key=payload.api_key,
            is_enabled=payload.is_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AIProviderConfigResponse(
        feature_enabled=get_ai_feature_enabled(),
        config=_config_summary_or_none(config),
    )


@router.post("/provider-config/health-check", response_model=AIProviderHealthResponse)
def post_provider_health_check(
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    config = get_instance_provider_config(db)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No AI provider is configured.")

    health = refresh_provider_health(db, config=config)
    return AIProviderHealthResponse(
        feature_enabled=get_ai_feature_enabled(),
        config=AIProviderConfigSummary.model_validate(serialize_provider_config(config)),
        health=AIProviderHealthSummary(
            status=health.status,
            is_healthy=health.is_healthy,
            message=health.message,
            models=health.models,
            capabilities=health.capabilities,
        ),
    )
