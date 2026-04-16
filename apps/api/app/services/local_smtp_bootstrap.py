from __future__ import annotations

import os
from dataclasses import dataclass

import structlog

from app.services.instance_settings import (
    _normalize_optional_text,
    _normalize_smtp_port,
    _require_valid_email,
    normalize_smtp_host,
    normalize_smtp_security,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class LocalSMTPBootstrapConfig:
    host: str
    port: int
    username: str | None
    password: str | None
    from_email: str | None
    from_name: str | None
    security: str
    is_enabled: bool
    test_recipient_email: str | None
    password_reset_enabled: bool


def _first_env_value(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return None


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_optional_port(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(value.strip())


def resolve_local_smtp_bootstrap_config() -> LocalSMTPBootstrapConfig | None:
    raw_host = _first_env_value("PANTRY_LOCAL_SMTP_HOST", "SMTP_HOST")
    if raw_host is None:
        return None

    try:
        security = normalize_smtp_security(_first_env_value("PANTRY_LOCAL_SMTP_SECURITY", "SMTP_SECURITY"))
        host = normalize_smtp_host(raw_host)
        if host is None:
            return None

        username = _normalize_optional_text(
            _first_env_value("PANTRY_LOCAL_SMTP_USERNAME", "SMTP_USERNAME")
        )
        password = _normalize_optional_text(
            _first_env_value("PANTRY_LOCAL_SMTP_PASSWORD", "SMTP_PASSWORD")
        )
        if username and not password:
            raise ValueError("An SMTP password is required when an SMTP username is configured.")
        if password and not username:
            raise ValueError("An SMTP username is required when an SMTP password is configured.")

        from_email = _normalize_optional_text(
            _first_env_value("PANTRY_LOCAL_SMTP_FROM_EMAIL", "SMTP_FROM_EMAIL")
        )
        test_recipient_email = _normalize_optional_text(
            _first_env_value("PANTRY_LOCAL_SMTP_TEST_RECIPIENT_EMAIL")
        )
        return LocalSMTPBootstrapConfig(
            host=host,
            port=_normalize_smtp_port(
                _parse_optional_port(_first_env_value("PANTRY_LOCAL_SMTP_PORT", "SMTP_PORT")),
                security=security,
            ),
            username=username,
            password=password,
            from_email=(
                _require_valid_email(from_email, field_name="SMTP from email")
                if from_email
                else None
            ),
            from_name=_normalize_optional_text(
                _first_env_value("PANTRY_LOCAL_SMTP_FROM_NAME", "SMTP_FROM_NAME")
            ),
            security=security,
            is_enabled=_parse_bool(
                _first_env_value("PANTRY_LOCAL_SMTP_ENABLED", "SMTP_ENABLED"),
                True,
            ),
            test_recipient_email=(
                _require_valid_email(test_recipient_email, field_name="SMTP test recipient email")
                if test_recipient_email
                else None
            ),
            password_reset_enabled=_parse_bool(
                _first_env_value("PANTRY_LOCAL_SMTP_PASSWORD_RESET_ENABLED"),
                False,
            ),
        )
    except ValueError as exc:
        logger.warning(
            "local_smtp_bootstrap.invalid_configuration",
            error=str(exc),
        )
        return None
