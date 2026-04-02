from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from time import perf_counter

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

WORKER_HEARTBEAT_KEY = "pantry:worker:heartbeat"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value: datetime) -> str:
    return value.isoformat()


def get_redis_client() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)


@dataclass(frozen=True)
class RedisHealthSnapshot:
    status: str
    latency_ms: float | None
    message: str | None = None


@dataclass(frozen=True)
class WorkerHeartbeat:
    service: str
    environment: str
    version: str
    mode: str
    poll_interval_seconds: int
    last_seen_at: datetime
    started_at: datetime
    status: str = "ok"


def publish_worker_heartbeat(
    *,
    service: str,
    environment: str,
    version: str,
    mode: str,
    poll_interval_seconds: int,
    started_at: datetime,
) -> None:
    heartbeat = WorkerHeartbeat(
        service=service,
        environment=environment,
        version=version,
        mode=mode,
        poll_interval_seconds=poll_interval_seconds,
        started_at=started_at,
        last_seen_at=utc_now(),
    )
    ttl_seconds = max(poll_interval_seconds * 3, 90)
    try:
        get_redis_client().setex(
            WORKER_HEARTBEAT_KEY,
            ttl_seconds,
            json.dumps(
                {
                    **asdict(heartbeat),
                    "started_at": _isoformat(heartbeat.started_at),
                    "last_seen_at": _isoformat(heartbeat.last_seen_at),
                }
            ),
        )
    except RedisError:
        return


def read_worker_heartbeat() -> dict[str, object] | None:
    try:
        payload = get_redis_client().get(WORKER_HEARTBEAT_KEY)
    except RedisError:
        return None
    if not payload:
        return None

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None

    return {
        **data,
        "started_at": datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
        "last_seen_at": datetime.fromisoformat(data["last_seen_at"]) if data.get("last_seen_at") else None,
    }


def check_redis_health() -> RedisHealthSnapshot:
    started = perf_counter()
    try:
        get_redis_client().ping()
    except RedisError as exc:
        return RedisHealthSnapshot(status="unavailable", latency_ms=None, message=str(exc))

    latency_ms = round((perf_counter() - started) * 1000, 2)
    return RedisHealthSnapshot(status="ok", latency_ms=latency_ms, message=None)
