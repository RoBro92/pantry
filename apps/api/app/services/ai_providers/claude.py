from __future__ import annotations

import json
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

ANTHROPIC_VERSION = "2023-06-01"


class ClaudeProviderAdapter:
    def __init__(self, config: AIProviderRuntimeConfig):
        self._config = config

    def _url(self, path: str) -> str:
        return urljoin(f"{self._config.base_url.rstrip('/')}/", path.lstrip("/"))

    def _headers(self) -> dict[str, str]:
        headers = {
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        if self._config.api_key:
            headers["x-api-key"] = self._config.api_key
        return headers

    def list_models(self) -> list[str]:
        with httpx.Client(timeout=self._config.timeout_seconds, headers=self._headers()) as client:
            response = client.get(self._url("/v1/models"))
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
        payload = {
            "model": request.model,
            "max_tokens": 4096,
            "temperature": request.temperature,
            "system": (
                f"{request.system_prompt} "
                "Return only JSON that matches the supplied schema. Do not wrap the JSON in markdown fences."
            ),
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "payload": request.user_payload,
                            "output_schema": request.output_schema,
                        }
                    ),
                }
            ],
        }

        with httpx.Client(timeout=self._config.timeout_seconds, headers=self._headers()) as client:
            response = client.post(self._url("/v1/messages"), json=payload)
            response.raise_for_status()
            body = response.json()

        output_text = "\n".join(
            block.get("text", "")
            for block in body.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
        parsed_output = parse_json_output(output_text)

        return StructuredCompletionResult(
            output_text=output_text,
            parsed_output=parsed_output,
            provider_request_id=body.get("id"),
        )
