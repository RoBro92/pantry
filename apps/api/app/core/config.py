import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_optional_bool(value: str | None) -> bool | None:
    if value is None or not value.strip():
        return None
    return _parse_bool(value, False)


def _parse_optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(value)


def _sanitize_url(value: str) -> str:
    if not value:
        return value

    parsed = urlsplit(value)
    if parsed.password is None:
        return value

    username = parsed.username or ""
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{username}:***@{host}{port}" if username else f"***@{host}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


@dataclass(frozen=True)
class AppSettings:
    service_name: str
    environment: str
    log_level: str
    app_version: str
    deployment_mode: str
    ai_feature_enabled: bool
    web_app_url: str
    api_base_url: str
    database_url: str
    redis_url: str
    settings_encryption_key: str | None
    import_storage_root: str
    import_max_upload_bytes: int
    session_secret_key: str
    session_cookie_name: str
    session_max_age_seconds: int
    session_https_only: bool
    session_same_site: str
    public_browser_base_url: str | None
    smtp_host: str | None
    smtp_port: int | None
    smtp_username: str | None
    smtp_password: str | None
    smtp_from_email: str | None
    smtp_from_name: str | None
    smtp_security: str | None
    smtp_enabled: bool | None
    smtp_timeout_seconds: int

    @property
    def cors_origins(self) -> list[str]:
        return [self.web_app_url]

    @property
    def safe_database_url(self) -> str:
        return _sanitize_url(self.database_url)

    @property
    def safe_redis_url(self) -> str:
        return _sanitize_url(self.redis_url)


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings(
        service_name=os.getenv("API_SERVICE_NAME", "pantry-api"),
        environment=os.getenv("ENVIRONMENT", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        deployment_mode=os.getenv("DEPLOYMENT_MODE", "self_hosted"),
        ai_feature_enabled=_parse_bool(os.getenv("AI_FEATURE_ENABLED"), True),
        web_app_url=os.getenv("WEB_APP_URL", "http://localhost:3000"),
        api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000"),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://pantry:change-me@postgres:5432/pantry",
        ),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        settings_encryption_key=os.getenv("SETTINGS_ENCRYPTION_KEY") or None,
        import_storage_root=os.getenv("IMPORT_STORAGE_ROOT", "/workspace/.local/imports"),
        import_max_upload_bytes=int(os.getenv("IMPORT_MAX_UPLOAD_BYTES", "10485760")),
        session_secret_key=os.getenv("SESSION_SECRET_KEY", "change-me-for-production"),
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "pantry_session"),
        session_max_age_seconds=int(os.getenv("SESSION_MAX_AGE_SECONDS", "604800")),
        session_https_only=_parse_bool(os.getenv("SESSION_HTTPS_ONLY"), False),
        session_same_site=os.getenv("SESSION_SAME_SITE", "lax"),
        public_browser_base_url=os.getenv("PUBLIC_BROWSER_BASE_URL") or None,
        smtp_host=os.getenv("SMTP_HOST") or None,
        smtp_port=_parse_optional_int(os.getenv("SMTP_PORT")),
        smtp_username=os.getenv("SMTP_USERNAME") or None,
        smtp_password=os.getenv("SMTP_PASSWORD") or None,
        smtp_from_email=os.getenv("SMTP_FROM_EMAIL") or None,
        smtp_from_name=os.getenv("SMTP_FROM_NAME") or None,
        smtp_security=os.getenv("SMTP_SECURITY") or None,
        smtp_enabled=_parse_optional_bool(os.getenv("SMTP_ENABLED")),
        smtp_timeout_seconds=int(os.getenv("SMTP_TIMEOUT_SECONDS", "5")),
    )
