from __future__ import annotations

from app.domain.ai import AI_PROVIDER_OLLAMA, AI_PROVIDER_OPENAI_COMPATIBLE
from app.services.ai_providers.base import AIProviderAdapter, AIProviderRuntimeConfig
from app.services.ai_providers.ollama import OllamaProviderAdapter
from app.services.ai_providers.openai_compatible import OpenAICompatibleProviderAdapter


def build_ai_provider_adapter(config: AIProviderRuntimeConfig) -> AIProviderAdapter:
    if config.provider_type == AI_PROVIDER_OLLAMA:
        return OllamaProviderAdapter(config)
    if config.provider_type == AI_PROVIDER_OPENAI_COMPATIBLE:
        return OpenAICompatibleProviderAdapter(config)
    raise ValueError(f"Unsupported AI provider type: {config.provider_type}")
