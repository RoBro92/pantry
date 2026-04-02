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
class WorkerSettings:
    service_name: str
    environment: str
    log_level: str
    app_version: str
    redis_url: str
    poll_interval_seconds: int
    run_once: bool

    @property
    def safe_redis_url(self) -> str:
        return _sanitize_url(self.redis_url)


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings(
        service_name=os.getenv("WORKER_SERVICE_NAME", "pantry-worker"),
        environment=os.getenv("ENVIRONMENT", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        poll_interval_seconds=int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "30")),
        run_once=os.getenv("WORKER_RUN_ONCE", "false").lower() == "true",
    )

