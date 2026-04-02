from __future__ import annotations

import json
from typing import Any
from urllib.parse import urljoin

import httpx

from app.domain.ai import AI_HEALTH_HEALTHY, AI_HEALTH_UNHEALTHY
from app.services.ai_providers.base import (
    AIProviderHealth,
    AIProviderRuntimeConfig,
    StructuredCompletionRequest,
    StructuredCompletionResult,
)


class OllamaProviderAdapter:
    def __init__(self, config: AIProviderRuntimeConfig):
        self._config = config

    def _url(self, path: str) -> str:
        return urljoin(f"{self._config.base_url.rstrip('/')}/", path.lstrip("/"))

    def list_models(self) -> list[str]:
        with httpx.Client(timeout=self._config.timeout_seconds) as client:
            response = client.get(self._url("/api/tags"))
            response.raise_for_status()
            payload = response.json()
        return sorted(
            [
                str(model["name"])
                for model in payload.get("models", [])
                if isinstance(model, dict) and model.get("name")
            ]
        )

    def check_health(self) -> AIProviderHealth:
        try:
            models = self.list_models()
            return AIProviderHealth(
                is_healthy=True,
                status=AI_HEALTH_HEALTHY,
                message=None,
                models=models,
                capabilities={
                    "supports_model_listing": True,
                    "supports_structured_output": True,
                },
            )
        except Exception as exc:
            return AIProviderHealth(
                is_healthy=False,
                status=AI_HEALTH_UNHEALTHY,
                message=str(exc),
                models=[],
                capabilities={
                    "supports_model_listing": True,
                    "supports_structured_output": True,
                },
            )

    def generate_structured_output(
        self,
        request: StructuredCompletionRequest,
    ) -> StructuredCompletionResult:
        payload: dict[str, Any] = {
            "model": request.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": json.dumps(request.user_payload)},
            ],
            "options": {
                "temperature": request.temperature,
            },
        }

        with httpx.Client(timeout=self._config.timeout_seconds) as client:
            response = client.post(self._url("/api/chat"), json=payload)
            response.raise_for_status()
            body = response.json()

        output_text = body.get("message", {}).get("content", "")
        if not output_text:
            raise ValueError("Provider returned an empty response.")

        return StructuredCompletionResult(
            output_text=output_text,
            parsed_output=json.loads(output_text),
            provider_request_id=None,
        )
