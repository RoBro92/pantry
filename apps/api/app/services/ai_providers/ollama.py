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
from app.services.ai_runtime import normalize_ai_error


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
                    "supports_manual_model_entry": True,
                },
            )
        except Exception as exc:
            error = normalize_ai_error(
                exc,
                provider_type=self._config.provider_type,
                model=self._config.default_model,
            )
            return AIProviderHealth(
                is_healthy=False,
                status=AI_HEALTH_UNHEALTHY,
                message=str(error),
                models=[],
                capabilities={
                    "supports_model_listing": True,
                    "supports_structured_output": True,
                    "supports_manual_model_entry": True,
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
        if request.max_output_tokens is not None:
            payload["options"]["num_predict"] = request.max_output_tokens

        with httpx.Client(timeout=request.timeout_seconds or self._config.timeout_seconds) as client:
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
