from __future__ import annotations

import secrets

from fastapi import Request

from app.core.config import get_settings

CLIENT_SCOPE_HEADER = "x-pantro-client-scope"
PROXY_TOKEN_HEADER = "x-pantro-proxy-token"
MAX_CLIENT_SCOPE_LENGTH = 128


def _first_header_value(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.split(",", 1)[0].strip()
    if not candidate or len(candidate) > MAX_CLIENT_SCOPE_LENGTH:
        return None
    if any(character in candidate for character in "\r\n\t"):
        return None
    return candidate


def _request_peer_scope(request: Request) -> str:
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


def client_scope_from_request(request: Request) -> str:
    settings = get_settings()
    proxy_token = settings.internal_api_proxy_token
    provided_token = request.headers.get(PROXY_TOKEN_HEADER)

    if proxy_token and provided_token and secrets.compare_digest(provided_token, proxy_token):
        proxy_scope = _first_header_value(request.headers.get(CLIENT_SCOPE_HEADER))
        if proxy_scope is not None:
            return proxy_scope

    return _request_peer_scope(request)
