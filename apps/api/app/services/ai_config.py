from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.ai import (
    AI_PROVIDER_CLAUDE,
    AI_PROVIDER_CUSTOM,
    AI_HEALTH_UNHEALTHY,
    AI_HEALTH_UNKNOWN,
    AI_PROVIDER_OLLAMA,
    AI_PROVIDER_OPENAI,
    AI_PROVIDER_OPENAI_COMPATIBLE,
    AI_PROVIDER_TYPES,
    AI_SCOPE_HOUSEHOLD,
    AI_SCOPE_INSTANCE,
    AI_SCOPE_KEY_INSTANCE,
)
from app.models.ai_provider_config import AIProviderConfig
from app.models.household import Household
from app.models.user import User
from app.services.ai_providers import AIProviderHealth, AIProviderRuntimeConfig, build_ai_provider_adapter
from app.services.audit import record_audit_event
from app.services.secrets import decrypt_secret, encrypt_secret


@dataclass(frozen=True)
class ResolvedAIProviderConfig:
    record: AIProviderConfig
    runtime: AIProviderRuntimeConfig


OPENAI_API_BASE_URL = "https://api.openai.com/v1"
OPENAI_API_BASE_URL_LEGACY = "https://api.openai.com"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if not normalized:
        raise ValueError("Provider base URL is required.")

    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Provider base URL must be a valid http or https URL.")
    if parsed.username or parsed.password:
        raise ValueError("Provider base URL must not embed credentials.")

    return normalized


def _provider_requires_api_key(provider_type: str) -> bool:
    return provider_type in {AI_PROVIDER_OPENAI, AI_PROVIDER_CLAUDE}


def _is_openai_base_url(base_url: str) -> bool:
    normalized = _normalize_base_url(base_url)
    return normalized in {OPENAI_API_BASE_URL, OPENAI_API_BASE_URL_LEGACY}


def normalize_provider_type(provider_type: str, *, base_url: str | None = None) -> str:
    if provider_type in AI_PROVIDER_TYPES:
        return provider_type

    if provider_type == AI_PROVIDER_OPENAI_COMPATIBLE:
        if base_url:
            try:
                if _is_openai_base_url(base_url):
                    return AI_PROVIDER_OPENAI
            except ValueError:
                pass
        return AI_PROVIDER_CUSTOM

    raise ValueError("Unsupported AI provider type.")


def has_selected_model(config: AIProviderConfig) -> bool:
    return bool(config.default_model.strip())


def provider_is_ready_for_runtime(config: AIProviderConfig) -> tuple[bool, str | None]:
    provider_type = normalize_provider_type(config.provider_type, base_url=config.base_url)
    if not config.base_url.strip():
        return False, "The configured AI provider does not have a base URL yet."
    if _provider_requires_api_key(provider_type) and not config.encrypted_api_key:
        return False, "The configured AI provider needs an API key before it can be used."
    if not has_selected_model(config):
        return False, "Choose a model for the configured AI provider before using AI suggestions."
    return True, None


def validate_provider_health_check_ready(config: AIProviderConfig) -> None:
    provider_type = normalize_provider_type(config.provider_type, base_url=config.base_url)
    if not config.base_url.strip():
        raise ValueError("Provider base URL is required before checking the connection.")
    if _provider_requires_api_key(provider_type) and not config.encrypted_api_key:
        raise ValueError("An API key is required before checking this provider connection.")


def _build_scope_key(*, scope_type: str, household: Household | None) -> str:
    if scope_type == AI_SCOPE_INSTANCE:
        return AI_SCOPE_KEY_INSTANCE
    if scope_type == AI_SCOPE_HOUSEHOLD and household is not None:
        return household.external_id
    raise ValueError("A household is required for household-scoped AI configuration.")


def get_ai_feature_enabled() -> bool:
    return get_settings().ai_feature_enabled


def get_provider_config_for_scope(
    db: Session,
    *,
    scope_type: str,
    household: Household | None = None,
) -> AIProviderConfig | None:
    scope_key = _build_scope_key(scope_type=scope_type, household=household)
    return db.scalar(
        select(AIProviderConfig)
        .where(AIProviderConfig.scope_type == scope_type)
        .where(AIProviderConfig.scope_key == scope_key)
    )


def resolve_provider_config(
    db: Session,
    *,
    household: Household,
) -> ResolvedAIProviderConfig | None:
    config = get_provider_config_for_scope(db, scope_type=AI_SCOPE_HOUSEHOLD, household=household)
    if config is None:
        config = get_provider_config_for_scope(db, scope_type=AI_SCOPE_INSTANCE)
    if config is None:
        return None

    api_key = decrypt_secret(config.encrypted_api_key) if config.encrypted_api_key else None
    provider_type = normalize_provider_type(config.provider_type, base_url=config.base_url)
    return ResolvedAIProviderConfig(
        record=config,
        runtime=AIProviderRuntimeConfig(
            provider_type=provider_type,
            base_url=config.base_url,
            default_model=config.default_model,
            api_key=api_key,
        ),
    )


def get_instance_provider_config(db: Session) -> AIProviderConfig | None:
    return get_provider_config_for_scope(db, scope_type=AI_SCOPE_INSTANCE)


def upsert_instance_provider_config(
    db: Session,
    *,
    actor: User,
    provider_type: str,
    base_url: str,
    default_model: str,
    api_key: str | None,
    is_enabled: bool,
) -> AIProviderConfig:
    if provider_type not in AI_PROVIDER_TYPES:
        raise ValueError("Unsupported AI provider type.")

    normalized_base_url = _normalize_base_url(base_url)
    normalized_model = default_model.strip()
    normalized_api_key = api_key.strip() if api_key else None

    config = get_instance_provider_config(db)
    created = config is None
    previous_provider_type = (
        normalize_provider_type(config.provider_type, base_url=config.base_url) if config is not None else None
    )
    if config is None:
        config = AIProviderConfig(
            scope_type=AI_SCOPE_INSTANCE,
            scope_key=AI_SCOPE_KEY_INSTANCE,
            provider_type=provider_type,
            base_url=normalized_base_url,
            default_model=normalized_model,
            is_enabled=is_enabled,
        )
        db.add(config)

    config.provider_type = provider_type
    config.base_url = normalized_base_url
    config.default_model = normalized_model
    config.is_enabled = is_enabled
    config.health_status = AI_HEALTH_UNKNOWN
    config.health_checked_at = None
    config.health_error = None
    config.available_model_count = 0
    config.capabilities = {}
    if normalized_api_key:
        config.encrypted_api_key = encrypt_secret(normalized_api_key)
    elif provider_type == AI_PROVIDER_OLLAMA or previous_provider_type != provider_type:
        config.encrypted_api_key = None

    db.add(config)
    db.flush()
    record_audit_event(
        db,
        household=None,
        actor=actor,
        action="ai.provider_config.saved",
        target_type="ai_provider_config",
        target_external_id=config.external_id,
        event_metadata={
            "scope_type": config.scope_type,
            "provider_type": config.provider_type,
            "base_url": config.base_url,
            "default_model": config.default_model,
            "has_api_key": bool(config.encrypted_api_key),
            "is_enabled": config.is_enabled,
            "created": created,
        },
    )
    db.commit()
    db.refresh(config)
    return config


def refresh_provider_health(
    db: Session,
    *,
    config: AIProviderConfig,
) -> AIProviderHealth:
    validate_provider_health_check_ready(config)
    api_key = decrypt_secret(config.encrypted_api_key) if config.encrypted_api_key else None
    provider_type = normalize_provider_type(config.provider_type, base_url=config.base_url)
    adapter = build_ai_provider_adapter(
        AIProviderRuntimeConfig(
            provider_type=provider_type,
            base_url=config.base_url,
            default_model=config.default_model,
            api_key=api_key,
        )
    )
    health = adapter.check_health()
    config.health_status = health.status
    config.health_checked_at = _utc_now()
    config.health_error = health.message
    config.available_model_count = len(health.models)
    config.capabilities = health.capabilities
    if health.is_healthy:
        config.last_success_at = _utc_now()
    db.add(config)
    db.commit()
    db.refresh(config)
    return health


def record_provider_runtime_failure(
    db: Session,
    *,
    config: AIProviderConfig,
    error_message: str,
) -> AIProviderConfig:
    config.health_status = AI_HEALTH_UNHEALTHY
    config.health_checked_at = _utc_now()
    config.health_error = error_message[:512]
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def serialize_provider_config(config: AIProviderConfig | None) -> dict[str, object] | None:
    if config is None:
        return None

    provider_type = normalize_provider_type(config.provider_type, base_url=config.base_url)
    return {
        "external_id": config.external_id,
        "scope_type": config.scope_type,
        "provider_type": provider_type,
        "base_url": config.base_url,
        "default_model": config.default_model,
        "is_enabled": config.is_enabled,
        "has_api_key": bool(config.encrypted_api_key),
        "health_status": config.health_status,
        "health_checked_at": config.health_checked_at,
        "health_error": config.health_error,
        "available_model_count": config.available_model_count,
        "capabilities": config.capabilities or {},
        "last_success_at": config.last_success_at,
        "updated_at": config.updated_at,
    }
