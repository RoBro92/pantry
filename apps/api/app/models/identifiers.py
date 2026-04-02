from __future__ import annotations

import secrets


def generate_external_id(prefix: str) -> str:
    token = secrets.token_urlsafe(12).rstrip("=")
    return f"{prefix}_{token}"

