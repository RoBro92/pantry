import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit


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
    web_app_url: str
    database_url: str
    redis_url: str

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
        web_app_url=os.getenv("WEB_APP_URL", "http://localhost:3000"),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://pantry:change-me@postgres:5432/pantry",
        ),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    )

