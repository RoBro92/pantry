from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parseaddr
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.instance_setting import InstanceSetting
from app.models.user import User
from app.services.audit import record_audit_event
from app.services.secrets import decrypt_secret, encrypt_secret

CONFIG_SOURCE_DATABASE = "database"
CONFIG_SOURCE_DEPLOYMENT = "deployment_default"
CONFIG_SOURCE_ENVIRONMENT = "environment"
SMTP_SECURITY_NONE = "none"
SMTP_SECURITY_SSL = "ssl"
SMTP_SECURITY_STARTTLS = "starttls"
SMTP_SECURITY_VALUES = {SMTP_SECURITY_NONE, SMTP_SECURITY_SSL, SMTP_SECURITY_STARTTLS}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_valid_email(value: str, *, field_name: str) -> str:
    candidate = value.strip()
    parsed_name, parsed_email = parseaddr(candidate)
    if not candidate or parsed_name or not parsed_email or "@" not in parsed_email:
        raise ValueError(f"{field_name} must be a valid email address.")
    return parsed_email


def normalize_public_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Public browser URL must be a valid http or https URL.")
    if parsed.username or parsed.password:
        raise ValueError("Public browser URL must not embed credentials.")
    return normalized


def normalize_smtp_security(value: str | None) -> str:
    normalized = (value or SMTP_SECURITY_STARTTLS).strip().lower()
    if normalized not in SMTP_SECURITY_VALUES:
        raise ValueError("SMTP security must be one of: none, starttls, ssl.")
    return normalized


def _normalize_smtp_port(value: int | None, *, security: str) -> int:
    if value is None:
        return 465 if security == SMTP_SECURITY_SSL else 587
    if value < 1 or value > 65535:
        raise ValueError("SMTP port must be between 1 and 65535.")
    return value


def normalize_smtp_host(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None

    parsed = urlsplit(f"//{normalized}")
    if parsed.username or parsed.password:
        raise ValueError("SMTP host must not include credentials.")
    if parsed.path or parsed.query or parsed.fragment:
        raise ValueError("SMTP host must not include a path, query string, or fragment.")
    if not parsed.hostname:
        raise ValueError("SMTP host must be a hostname or IP address.")
    if parsed.port is not None:
        raise ValueError("SMTP host must not include a port. Use the SMTP port field separately.")
    return parsed.hostname


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


@dataclass(frozen=True)
class PublicBaseURLState:
    stored_value: str | None
    effective_value: str
    effective_source: str


@dataclass(frozen=True)
class SMTPResolvedConfig:
    host: str | None
    port: int | None
    username: str | None
    password: str | None
    from_email: str | None
    from_name: str | None
    security: str | None
    is_enabled: bool
    source: str
    last_test_status: str
    last_tested_at: datetime | None
    last_test_error: str | None
    stored_host: str | None
    stored_port: int | None
    stored_username: str | None
    stored_has_password: bool
    stored_from_email: str | None
    stored_from_name: str | None
    stored_security: str | None
    stored_is_enabled: bool
    config_error: str | None = None

    @property
    def has_password(self) -> bool:
        return bool(self.password)

    @property
    def is_configured(self) -> bool:
        if not self.host or self.port is None or not self.from_email:
            return False
        if bool(self.username) != bool(self.password):
            return False
        return True


def get_instance_settings(db: Session) -> InstanceSetting | None:
    return db.scalar(select(InstanceSetting).where(InstanceSetting.scope_key == "instance"))


def get_or_create_instance_settings(db: Session) -> InstanceSetting:
    settings = get_instance_settings(db)
    if settings is None:
        settings = InstanceSetting(scope_key="instance")
        db.add(settings)
        db.flush()
    return settings


def resolve_public_base_url(db: Session) -> PublicBaseURLState:
    app_settings = get_settings()
    stored = get_instance_settings(db)
    stored_value = stored.public_base_url if stored else None

    if app_settings.public_browser_base_url:
        return PublicBaseURLState(
            stored_value=stored_value,
            effective_value=normalize_public_base_url(app_settings.public_browser_base_url),
            effective_source=CONFIG_SOURCE_ENVIRONMENT,
        )
    if stored_value:
        return PublicBaseURLState(
            stored_value=stored_value,
            effective_value=normalize_public_base_url(stored_value),
            effective_source=CONFIG_SOURCE_DATABASE,
        )
    return PublicBaseURLState(
        stored_value=None,
        effective_value=normalize_public_base_url(app_settings.web_app_url),
        effective_source=CONFIG_SOURCE_DEPLOYMENT,
    )


def upsert_public_base_url(
    db: Session,
    *,
    actor: User,
    public_base_url: str,
) -> InstanceSetting:
    settings = get_or_create_instance_settings(db)
    settings.public_base_url = normalize_public_base_url(public_base_url)
    db.add(settings)
    db.flush()
    record_audit_event(
        db,
        household=None,
        actor=actor,
        action="instance.public_base_url.saved",
        target_type="instance_setting",
        target_external_id=settings.external_id,
        event_metadata={"public_base_url": settings.public_base_url},
    )
    db.commit()
    db.refresh(settings)
    return settings


def build_public_base_url_summary(db: Session) -> dict[str, object]:
    state = resolve_public_base_url(db)
    return {
        "stored_value": state.stored_value,
        "effective_value": state.effective_value,
        "effective_source": state.effective_source,
    }


def _build_smtp_config_from_db(stored: InstanceSetting | None) -> SMTPResolvedConfig:
    password = decrypt_secret(stored.encrypted_smtp_password) if stored and stored.encrypted_smtp_password else None
    return SMTPResolvedConfig(
        host=stored.smtp_host if stored else None,
        port=stored.smtp_port if stored else None,
        username=stored.smtp_username if stored else None,
        password=password,
        from_email=stored.smtp_from_email if stored else None,
        from_name=stored.smtp_from_name if stored else None,
        security=stored.smtp_security if stored else None,
        is_enabled=stored.smtp_enabled if stored else False,
        source=CONFIG_SOURCE_DATABASE,
        last_test_status=stored.smtp_last_test_status if stored else "never",
        last_tested_at=stored.smtp_last_tested_at if stored else None,
        last_test_error=stored.smtp_last_test_error if stored else None,
        stored_host=stored.smtp_host if stored else None,
        stored_port=stored.smtp_port if stored else None,
        stored_username=stored.smtp_username if stored else None,
        stored_has_password=bool(stored and stored.encrypted_smtp_password),
        stored_from_email=stored.smtp_from_email if stored else None,
        stored_from_name=stored.smtp_from_name if stored else None,
        stored_security=stored.smtp_security if stored else None,
        stored_is_enabled=stored.smtp_enabled if stored else False,
        config_error=None,
    )


def resolve_smtp_config(db: Session) -> SMTPResolvedConfig:
    app_settings = get_settings()
    stored = get_instance_settings(db)
    db_config = _build_smtp_config_from_db(stored)

    if app_settings.smtp_host:
        try:
            security = normalize_smtp_security(app_settings.smtp_security)
            host = normalize_smtp_host(app_settings.smtp_host)
            username = _normalize_optional_text(app_settings.smtp_username)
            password = _normalize_optional_text(app_settings.smtp_password)
            if username and not password:
                raise ValueError("An SMTP password is required when an SMTP username is configured.")
            if password and not username:
                raise ValueError("An SMTP username is required when an SMTP password is configured.")
            return SMTPResolvedConfig(
                host=host,
                port=_normalize_smtp_port(app_settings.smtp_port, security=security),
                username=username,
                password=password,
                from_email=_require_valid_email(
                    app_settings.smtp_from_email or "",
                    field_name="SMTP from email",
                )
                if app_settings.smtp_from_email
                else None,
                from_name=_normalize_optional_text(app_settings.smtp_from_name),
                security=security,
                is_enabled=True if app_settings.smtp_enabled is None else app_settings.smtp_enabled,
                source=CONFIG_SOURCE_ENVIRONMENT,
                last_test_status=db_config.last_test_status,
                last_tested_at=db_config.last_tested_at,
                last_test_error=db_config.last_test_error,
                stored_host=db_config.stored_host,
                stored_port=db_config.stored_port,
                stored_username=db_config.stored_username,
                stored_has_password=db_config.stored_has_password,
                stored_from_email=db_config.stored_from_email,
                stored_from_name=db_config.stored_from_name,
                stored_security=db_config.stored_security,
                stored_is_enabled=db_config.stored_is_enabled,
                config_error=None,
            )
        except ValueError as exc:
            return SMTPResolvedConfig(
                host=_normalize_optional_text(app_settings.smtp_host),
                port=app_settings.smtp_port,
                username=_normalize_optional_text(app_settings.smtp_username),
                password=_normalize_optional_text(app_settings.smtp_password),
                from_email=_normalize_optional_text(app_settings.smtp_from_email),
                from_name=_normalize_optional_text(app_settings.smtp_from_name),
                security=_normalize_optional_text(app_settings.smtp_security),
                is_enabled=False,
                source=CONFIG_SOURCE_ENVIRONMENT,
                last_test_status=db_config.last_test_status,
                last_tested_at=db_config.last_tested_at,
                last_test_error=db_config.last_test_error,
                stored_host=db_config.stored_host,
                stored_port=db_config.stored_port,
                stored_username=db_config.stored_username,
                stored_has_password=db_config.stored_has_password,
                stored_from_email=db_config.stored_from_email,
                stored_from_name=db_config.stored_from_name,
                stored_security=db_config.stored_security,
                stored_is_enabled=db_config.stored_is_enabled,
                config_error=str(exc),
            )

    return db_config


def build_smtp_summary(db: Session) -> dict[str, object]:
    config = resolve_smtp_config(db)
    return {
        "effective": {
            "host": config.host,
            "port": config.port,
            "username": config.username,
            "has_password": config.has_password,
            "from_email": config.from_email,
            "from_name": config.from_name,
            "security": config.security,
            "is_enabled": config.is_enabled,
        },
        "effective_source": config.source,
        "stored": {
            "host": config.stored_host,
            "port": config.stored_port,
            "username": config.stored_username,
            "has_password": config.stored_has_password,
            "from_email": config.stored_from_email,
            "from_name": config.stored_from_name,
            "security": config.stored_security,
            "is_enabled": config.stored_is_enabled,
        },
        "configured": config.is_configured,
        "config_error": config.config_error,
        "last_test_status": config.last_test_status,
        "last_tested_at": config.last_tested_at,
        "last_test_error": config.last_test_error,
    }


def upsert_smtp_settings(
    db: Session,
    *,
    actor: User,
    host: str | None,
    port: int | None,
    username: str | None,
    password: str | None,
    from_email: str | None,
    from_name: str | None,
    security: str | None,
    is_enabled: bool,
) -> InstanceSetting:
    settings = get_or_create_instance_settings(db)
    normalized_host = normalize_smtp_host(host)
    normalized_username = _normalize_optional_text(username)
    normalized_password = _normalize_optional_text(password)
    normalized_from_email = _normalize_optional_text(from_email)
    normalized_from_name = _normalize_optional_text(from_name)

    if not normalized_host:
        if any([normalized_username, normalized_password, normalized_from_email, normalized_from_name, port, security]):
            raise ValueError("SMTP host is required when saving SMTP configuration.")
        settings.smtp_host = None
        settings.smtp_port = None
        settings.smtp_username = None
        settings.encrypted_smtp_password = None
        settings.smtp_from_email = None
        settings.smtp_from_name = None
        settings.smtp_security = None
        settings.smtp_enabled = False
    else:
        normalized_security = normalize_smtp_security(security)
        settings.smtp_host = normalized_host
        settings.smtp_port = _normalize_smtp_port(port, security=normalized_security)
        settings.smtp_username = normalized_username
        settings.smtp_from_email = (
            _require_valid_email(normalized_from_email, field_name="SMTP from email")
            if normalized_from_email
            else None
        )
        settings.smtp_from_name = normalized_from_name
        settings.smtp_security = normalized_security
        settings.smtp_enabled = is_enabled

        existing_password = decrypt_secret(settings.encrypted_smtp_password) if settings.encrypted_smtp_password else None
        effective_password = normalized_password or (existing_password if normalized_username else None)
        if normalized_username and not effective_password:
            raise ValueError("An SMTP password is required when an SMTP username is configured.")
        if effective_password and not normalized_username:
            raise ValueError("An SMTP username is required when an SMTP password is configured.")

        if normalized_password:
            settings.encrypted_smtp_password = encrypt_secret(normalized_password)
        elif normalized_username is None:
            settings.encrypted_smtp_password = None

    settings.smtp_last_test_status = "never"
    settings.smtp_last_tested_at = None
    settings.smtp_last_test_error = None

    db.add(settings)
    db.flush()
    record_audit_event(
        db,
        household=None,
        actor=actor,
        action="smtp.config.saved",
        target_type="instance_setting",
        target_external_id=settings.external_id,
        event_metadata={
            "host": settings.smtp_host,
            "port": settings.smtp_port,
            "username": settings.smtp_username,
            "has_password": bool(settings.encrypted_smtp_password),
            "from_email": settings.smtp_from_email,
            "from_name": settings.smtp_from_name,
            "security": settings.smtp_security,
            "is_enabled": settings.smtp_enabled,
        },
    )
    db.commit()
    db.refresh(settings)
    return settings


def record_smtp_test_result(
    db: Session,
    *,
    actor: User,
    status: str,
    error: str | None,
) -> InstanceSetting:
    settings = get_or_create_instance_settings(db)
    settings.smtp_last_test_status = status
    settings.smtp_last_tested_at = _utc_now()
    settings.smtp_last_test_error = error
    db.add(settings)
    db.flush()
    record_audit_event(
        db,
        household=None,
        actor=actor,
        action="smtp.config.tested",
        target_type="instance_setting",
        target_external_id=settings.external_id,
        event_metadata={"status": status, "error": error},
    )
    db.commit()
    db.refresh(settings)
    return settings
