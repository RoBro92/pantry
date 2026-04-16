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

ANTHROPIC_VERSION = "2023-06-01"
STRUCTURED_OUTPUT_TOOL_NAME = "pantry_structured_output"


class ClaudeProviderAdapter:
    def __init__(self, config: AIProviderRuntimeConfig):
        self._config = config

    def _url(self, path: str) -> str:
        base = self._config.base_url.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return urljoin(f"{base}/", path.lstrip("/"))

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
            response = client.get(self._url("/models"), params={"limit": 1000})
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
                    "structured_output_mode": "tool_use",
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
                    "structured_output_mode": "tool_use",
                },
            )

    def generate_structured_output(
        self,
        request: StructuredCompletionRequest,
    ) -> StructuredCompletionResult:
        payload: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_output_tokens or 1200,
            "system": request.system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(request.user_payload),
                }
            ],
            "temperature": request.temperature,
            "tools": [
                {
                    "name": STRUCTURED_OUTPUT_TOOL_NAME,
                    "description": "Return the Pantro AI response in the expected structured format.",
                    "input_schema": request.output_schema,
                }
            ],
            "tool_choice": {
                "type": "tool",
                "name": STRUCTURED_OUTPUT_TOOL_NAME,
            },
        }

        with httpx.Client(
            timeout=request.timeout_seconds or self._config.timeout_seconds,
            headers=self._headers(),
        ) as client:
            response = client.post(self._url("/messages"), json=payload)
            response.raise_for_status()
            body = response.json()

        for block in body.get("content", []):
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_use"
                and block.get("name") == STRUCTURED_OUTPUT_TOOL_NAME
                and isinstance(block.get("input"), dict)
            ):
                parsed_output = block["input"]
                return StructuredCompletionResult(
                    output_text=json.dumps(parsed_output),
                    parsed_output=parsed_output,
                    provider_request_id=body.get("id"),
                )

        raise ValueError("Claude did not return the structured response tool payload.")
