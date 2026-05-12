from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import Request

from app.core.config import AppSettings

UNSAFE_METHODS = {"DELETE", "PATCH", "POST", "PUT"}


def _origin_from_url(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    try:
        parsed = urlsplit(normalized)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    host = parsed.hostname or ""
    try:
        parsed_port = parsed.port
    except ValueError:
        return None
    port = f":{parsed_port}" if parsed_port is not None else ""
    return f"{parsed.scheme.lower()}://{host.lower()}{port}"


def request_passes_csrf_origin_check(request: Request, settings: AppSettings) -> bool:
    if not settings.csrf_protection_enabled:
        return True
    if request.method.upper() not in UNSAFE_METHODS:
        return True
    if not request.url.path.startswith("/api/"):
        return True

    origin = _origin_from_url(request.headers.get("origin"))
    referer = _origin_from_url(request.headers.get("referer"))
    candidate = origin or referer
    if candidate is None:
        return False

    return candidate in settings.csrf_allowed_origins
