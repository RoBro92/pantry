from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.services.runtime_status import get_redis_client

RATE_LIMIT_PREFIX = "pantro:rate-limit"

_LOCAL_BUCKETS: dict[str, tuple[int, float]] = {}


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    attempts: int
    limit: int
    retry_after_seconds: int


def clear_local_rate_limits() -> None:
    _LOCAL_BUCKETS.clear()


def _hash_part(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def _build_key(scope: str, *parts: str) -> str:
    hashed_parts = ":".join(_hash_part(part) for part in parts if part)
    return f"{RATE_LIMIT_PREFIX}:{scope}:{hashed_parts or 'global'}"


def _hit_local_limit(key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
    now = time.time()
    attempts, expires_at = _LOCAL_BUCKETS.get(key, (0, now + window_seconds))
    if expires_at <= now:
        attempts = 0
        expires_at = now + window_seconds
    attempts += 1
    _LOCAL_BUCKETS[key] = (attempts, expires_at)
    retry_after = max(1, int(expires_at - now))
    return RateLimitResult(
        allowed=attempts <= limit,
        attempts=attempts,
        limit=limit,
        retry_after_seconds=retry_after,
    )


def _get_redis_client_or_none() -> Redis | None:
    try:
        return get_redis_client()
    except (RedisError, OSError, TimeoutError, ValueError):
        return None


def hit_rate_limit(
    scope: str,
    *parts: str,
    limit: int,
    window_seconds: int,
) -> RateLimitResult:
    key = _build_key(scope, *parts)
    if limit <= 0:
        return RateLimitResult(allowed=False, attempts=1, limit=limit, retry_after_seconds=window_seconds)

    settings = get_settings()
    if not settings.rate_limit_redis_enabled:
        return _hit_local_limit(key, limit=limit, window_seconds=window_seconds)

    client = _get_redis_client_or_none()
    if client is None:
        return _hit_local_limit(key, limit=limit, window_seconds=window_seconds)

    try:
        attempts = int(client.incr(key))
        if attempts == 1:
            client.expire(key, window_seconds)
        redis_ttl = client.ttl(key)
        retry_after = redis_ttl if redis_ttl and redis_ttl > 0 else window_seconds
        return RateLimitResult(
            allowed=attempts <= limit,
            attempts=attempts,
            limit=limit,
            retry_after_seconds=retry_after,
        )
    except (RedisError, OSError, TimeoutError, ValueError):
        return _hit_local_limit(key, limit=limit, window_seconds=window_seconds)
    finally:
        client.close()


def clear_rate_limit(scope: str, *parts: str) -> None:
    key = _build_key(scope, *parts)
    _LOCAL_BUCKETS.pop(key, None)

    if not get_settings().rate_limit_redis_enabled:
        return

    client = _get_redis_client_or_none()
    if client is None:
        return

    try:
        client.delete(key)
    except (RedisError, OSError, TimeoutError, ValueError):
        return
    finally:
        client.close()
