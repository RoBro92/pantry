from __future__ import annotations

from app.domain.ai import (
    AI_PROVIDER_CLAUDE,
    AI_PROVIDER_GEMINI,
    AI_PROVIDER_LITELLM,
    AI_PROVIDER_OLLAMA,
    AI_PROVIDER_OPENAI,
    AI_PROVIDER_OPENROUTER,
    canonical_provider_type,
)
from app.services.ai_providers.base import AIProviderAdapter, AIProviderRuntimeConfig
from app.services.ai_providers.claude import ClaudeProviderAdapter
from app.services.ai_providers.gemini import GeminiProviderAdapter
from app.services.ai_providers.ollama import OllamaProviderAdapter
from app.services.ai_providers.openai import OpenAIProviderAdapter


def build_ai_provider_adapter(config: AIProviderRuntimeConfig) -> AIProviderAdapter:
    provider_type = canonical_provider_type(config.provider_type)
    if provider_type == AI_PROVIDER_OLLAMA:
        return OllamaProviderAdapter(config)
    if provider_type in {AI_PROVIDER_OPENAI, AI_PROVIDER_OPENROUTER, AI_PROVIDER_LITELLM}:
        return OpenAIProviderAdapter(config)
    if provider_type == AI_PROVIDER_CLAUDE:
        return ClaudeProviderAdapter(config)
    if provider_type == AI_PROVIDER_GEMINI:
        return GeminiProviderAdapter(config)
    raise ValueError(f"Unsupported AI provider type: {config.provider_type}")
