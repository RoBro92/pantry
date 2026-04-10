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
from app.services.ai_providers.common import parse_json_output


class OpenAIProviderAdapter:
    def __init__(self, config: AIProviderRuntimeConfig):
        self._config = config

    def _url(self, path: str) -> str:
        return urljoin(f"{self._config.base_url.rstrip('/')}/", path.lstrip("/"))

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self._config.api_key:
            headers["authorization"] = f"Bearer {self._config.api_key}"
        return headers

    def list_models(self) -> list[str]:
        with httpx.Client(timeout=self._config.timeout_seconds, headers=self._headers()) as client:
            response = client.get(self._url("/models"))
            response.raise_for_status()
            payload = response.json()
        return sorted(
            [
                str(model["id"])
                for model in payload.get("data", [])
                if isinstance(model, dict) and model.get("id")
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
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": json.dumps(request.user_payload)},
            ],
            "temperature": request.temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "pantry_ai_response",
                    "strict": True,
                    "schema": request.output_schema,
                },
            },
        }

        with httpx.Client(timeout=self._config.timeout_seconds, headers=self._headers()) as client:
            response = client.post(self._url("/chat/completions"), json=payload)
            response.raise_for_status()
            body = response.json()

        choice = (body.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        output_text = message.get("content", "")
        parsed_output = parse_json_output(output_text)

        return StructuredCompletionResult(
            output_text=output_text,
            parsed_output=parsed_output,
            provider_request_id=body.get("id"),
        )
