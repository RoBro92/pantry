from __future__ import annotations

import json
from urllib.parse import quote, urljoin

import httpx

from app.domain.ai import AI_HEALTH_HEALTHY, AI_HEALTH_UNHEALTHY
from app.services.ai_providers.base import (
    AIUsageMetrics,
    AIProviderHealth,
    AIProviderRuntimeConfig,
    StructuredCompletionRequest,
    StructuredCompletionResult,
)
from app.services.ai_providers.common import parse_json_output
from app.services.ai_runtime import normalize_ai_error


class GeminiProviderAdapter:
    def __init__(self, config: AIProviderRuntimeConfig):
        self._config = config

    def _url(self, path: str) -> str:
        return urljoin(f"{self._config.base_url.rstrip('/')}/", path.lstrip("/"))

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self._config.api_key:
            headers["x-goog-api-key"] = self._config.api_key
        return headers

    def list_models(self) -> list[str]:
        with httpx.Client(timeout=self._config.timeout_seconds, headers=self._headers()) as client:
            response = client.get(self._url("/v1beta/models"))
            response.raise_for_status()
            payload = response.json()
        return sorted(
            [
                str(model.get("baseModelId") or str(model["name"]).removeprefix("models/"))
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
                },
            )

    def generate_structured_output(
        self,
        request: StructuredCompletionRequest,
    ) -> StructuredCompletionResult:
        model = request.model.removeprefix("models/")
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            f"{request.system_prompt} "
                            "Return only JSON that matches the supplied schema. Do not wrap the JSON in markdown fences."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "payload": request.user_payload,
                                    "output_schema": request.output_schema,
                                }
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": request.temperature,
                "responseMimeType": "application/json",
            },
        }
        if request.max_output_tokens is not None:
            payload["generationConfig"]["maxOutputTokens"] = request.max_output_tokens

        with httpx.Client(
            timeout=request.timeout_seconds or self._config.timeout_seconds,
            headers=self._headers(),
        ) as client:
            response = client.post(
                self._url(f"/v1beta/models/{quote(model, safe='')}:generateContent"),
                json=payload,
            )
            response.raise_for_status()
            body = response.json()

        output_text = "\n".join(
            part.get("text", "")
            for candidate in body.get("candidates", [])
            if isinstance(candidate, dict)
            for part in (candidate.get("content", {}).get("parts") or [])
            if isinstance(part, dict) and part.get("text")
        ).strip()
        parsed_output = parse_json_output(output_text)

        return StructuredCompletionResult(
            output_text=output_text,
            parsed_output=parsed_output,
            provider_request_id=body.get("responseId"),
            usage=_extract_gemini_usage(body),
        )


def _extract_gemini_usage(body: dict[str, object]) -> AIUsageMetrics | None:
    usage = body.get("usageMetadata")
    if not isinstance(usage, dict):
        return None

    input_tokens = usage.get("promptTokenCount")
    output_tokens = usage.get("candidatesTokenCount")
    total_tokens = usage.get("totalTokenCount")
    if not any(isinstance(value, int) for value in (input_tokens, output_tokens, total_tokens)):
        return None

    return AIUsageMetrics(
        input_tokens=input_tokens if isinstance(input_tokens, int) else None,
        output_tokens=output_tokens if isinstance(output_tokens, int) else None,
        total_tokens=total_tokens if isinstance(total_tokens, int) else None,
    )
