from __future__ import annotations

import os
from dataclasses import dataclass

from app.domain.ai import (
    AI_PROVIDER_API_KEY_REQUIRED,
    AI_PROVIDER_CLAUDE,
    AI_PROVIDER_DEFAULT_BASE_URLS,
    AI_PROVIDER_GEMINI,
    AI_PROVIDER_OLLAMA,
    AI_PROVIDER_OPENAI,
    AI_PROVIDER_TYPES,
    canonical_provider_type,
)
from app.services.ai_config import _normalize_base_url

DEFAULT_LOCAL_AI_MODELS = {
    AI_PROVIDER_OPENAI: "gpt-5.4-mini",
    AI_PROVIDER_CLAUDE: "claude-sonnet-4-6",
    AI_PROVIDER_GEMINI: "gemini-2.5-flash",
    AI_PROVIDER_OLLAMA: "qwen3:8b",
}


@dataclass(frozen=True)
class LocalAIBootstrapConfig:
    provider_type: str
    base_url: str
    default_model: str
    api_key: str | None


def _first_non_empty_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def resolve_local_ai_bootstrap_config() -> LocalAIBootstrapConfig | None:
    provider_type = canonical_provider_type(
        _first_non_empty_env("PANTRO_LOCAL_AI_PROVIDER_TYPE", "PANTRY_LOCAL_AI_PROVIDER_TYPE")
    )
    if provider_type is None:
        provider_type = AI_PROVIDER_OPENAI
    if provider_type not in AI_PROVIDER_TYPES:
        return None

    base_url = _first_non_empty_env("PANTRO_LOCAL_AI_BASE_URL", "PANTRY_LOCAL_AI_BASE_URL")
    api_key = _first_non_empty_env("PANTRO_LOCAL_AI_API_KEY", "PANTRY_LOCAL_AI_API_KEY")

    if provider_type == AI_PROVIDER_OPENAI:
        base_url = base_url or _first_non_empty_env("OPENAI_COMPAT_BASE_URL")
        api_key = api_key or _first_non_empty_env("OPENAI_COMPAT_API_KEY")

    default_model = _first_non_empty_env(
        "PANTRO_LOCAL_AI_DEFAULT_MODEL",
        "PANTRY_LOCAL_AI_DEFAULT_MODEL",
    ) or DEFAULT_LOCAL_AI_MODELS[provider_type]
    if not default_model:
        return None

    normalized_base_url = base_url or AI_PROVIDER_DEFAULT_BASE_URLS[provider_type]
    try:
        normalized_base_url = _normalize_base_url(normalized_base_url)
    except ValueError:
        return None

    if AI_PROVIDER_API_KEY_REQUIRED[provider_type] and not api_key:
        return None

    return LocalAIBootstrapConfig(
        provider_type=provider_type,
        base_url=normalized_base_url,
        default_model=default_model,
        api_key=api_key,
    )
