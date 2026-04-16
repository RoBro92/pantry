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
from app.services.ai_providers.errors import AIProviderError
from app.services.ai_providers.openai_compat import (
    OPENAI_RECOMMENDED_MODELS,
    extract_openai_message_text,
    extract_openai_refusal,
    is_openai_output_token_parameter_error,
    map_openai_http_error,
    map_openai_transport_error,
    normalize_openai_json_schema,
    openai_output_token_parameter_name,
    openai_model_profile,
    recommended_openai_models_text,
)


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

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        try:
            with httpx.Client(
                timeout=timeout_seconds or self._config.timeout_seconds,
                headers=self._headers(),
            ) as client:
                response = client.request(method, self._url(path), json=json_body)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise map_openai_http_error(exc, model=model or self._config.default_model) from exc
        except httpx.HTTPError as exc:
            raise map_openai_transport_error(exc) from exc
        except ValueError as exc:
            raise AIProviderError(
                "OpenAI returned a response Pantry could not read.",
                diagnostic_message=str(exc),
                category="invalid_response",
            ) from exc

        if not isinstance(payload, dict):
            raise AIProviderError(
                "OpenAI returned a response Pantry could not read.",
                diagnostic_message=f"Unexpected response body type: {type(payload).__name__}",
                category="invalid_response",
            )
        return payload

    def _build_payload(
        self,
        request: StructuredCompletionRequest,
        *,
        output_token_parameter_name: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(request.user_payload, separators=(",", ":"), ensure_ascii=False),
                },
            ],
            "temperature": request.temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": True,
                    "schema": normalize_openai_json_schema(request.output_schema),
                },
            },
        }
        if request.max_output_tokens is not None:
            token_parameter = output_token_parameter_name or openai_output_token_parameter_name(request.model)
            payload[token_parameter] = request.max_output_tokens
        return payload

    def _parse_completion_response(self, body: dict[str, Any], *, model: str) -> StructuredCompletionResult:
        choice = (body.get("choices") or [{}])[0]
        if not isinstance(choice, dict):
            raise AIProviderError(
                "OpenAI returned a response Pantry could not read.",
                diagnostic_message="choices[0] was not an object",
                category="invalid_response",
            )

        message = choice.get("message") or {}
        if not isinstance(message, dict):
            raise AIProviderError(
                "OpenAI returned a response Pantry could not read.",
                diagnostic_message="choices[0].message was not an object",
                category="invalid_response",
            )

        refusal = extract_openai_refusal(message)
        if refusal:
            raise AIProviderError(
                "OpenAI refused this Pantry AI request. Try a simpler request or switch to a recommended OpenAI model.",
                diagnostic_message=refusal,
                category="refusal",
            )

        output_text = extract_openai_message_text(message)
        if not output_text:
            raise AIProviderError(
                "OpenAI returned an empty structured response.",
                diagnostic_message=json.dumps(body)[:1000],
                category="invalid_response",
            )

        try:
            parsed_output = parse_json_output(output_text)
        except Exception as exc:
            raise AIProviderError(
                "OpenAI returned a structured response Pantry could not validate.",
                diagnostic_message=f"Could not parse model {model} response: {output_text[:1000]}",
                category="invalid_response",
            ) from exc

        return StructuredCompletionResult(
            output_text=output_text,
            parsed_output=parsed_output,
            provider_request_id=body.get("id"),
        )

    def _run_structured_completion(
        self,
        request: StructuredCompletionRequest,
    ) -> StructuredCompletionResult:
        token_parameter = openai_output_token_parameter_name(request.model)
        try:
            return self._run_structured_completion_once(
                request,
                output_token_parameter_name=token_parameter,
            )
        except AIProviderError as exc:
            if request.max_output_tokens is None or not is_openai_output_token_parameter_error(exc.diagnostic_message):
                raise
            alternate_parameter = "max_completion_tokens" if token_parameter == "max_tokens" else "max_tokens"
            return self._run_structured_completion_once(
                request,
                output_token_parameter_name=alternate_parameter,
            )

    def _run_structured_completion_once(
        self,
        request: StructuredCompletionRequest,
        *,
        output_token_parameter_name: str | None,
    ) -> StructuredCompletionResult:
        payload = self._build_payload(
            request,
            output_token_parameter_name=output_token_parameter_name,
        )
        body = self._request_json(
            "POST",
            "/chat/completions",
            json_body=payload,
            model=request.model,
            timeout_seconds=request.timeout_seconds,
        )
        return self._parse_completion_response(body, model=request.model)

    def _run_health_probe(self) -> None:
        probe = self._run_structured_completion(
            StructuredCompletionRequest(
                model=self._config.default_model,
                schema_name="pantry_openai_health_check",
                system_prompt=(
                    "Return only JSON for Pantry's OpenAI compatibility probe. "
                    "Set status to ok."
                ),
                user_payload={"probe": "pantry_openai_compatibility"},
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["ok"],
                        }
                    },
                    "required": ["status"],
                    "additionalProperties": False,
                },
                temperature=0,
            )
        )
        if probe.parsed_output.get("status") != "ok":
            raise AIProviderError(
                "OpenAI returned an unexpected compatibility probe response.",
                diagnostic_message=json.dumps(probe.parsed_output)[:1000],
                category="invalid_response",
            )

    def list_models(self) -> list[str]:
        payload = self._request_json("GET", "/models", model=self._config.default_model)
        return sorted(
            [
                str(model["id"])
                for model in payload.get("data", [])
                if isinstance(model, dict) and model.get("id")
            ]
        )

    def check_health(self) -> AIProviderHealth:
        models: list[str] = []
        capabilities = {
            "supports_model_listing": True,
            "supports_structured_output": True,
            "supports_manual_model_entry": True,
            "structured_output_mode": "chat_completions_json_schema",
            "recommended_models": list(OPENAI_RECOMMENDED_MODELS),
            "default_model_profile": openai_model_profile(self._config.default_model),
        }
        try:
            models = self.list_models()
            self._run_health_probe()
            return AIProviderHealth(
                is_healthy=True,
                status=AI_HEALTH_HEALTHY,
                message=None,
                models=models,
                capabilities=capabilities,
            )
        except AIProviderError as exc:
            return AIProviderHealth(
                is_healthy=False,
                status=AI_HEALTH_UNHEALTHY,
                message=exc.user_message,
                models=models,
                capabilities=capabilities,
            )
        except Exception:
            return AIProviderHealth(
                is_healthy=False,
                status=AI_HEALTH_UNHEALTHY,
                message=(
                    "Pantry could not verify OpenAI structured-output compatibility. "
                    f"Choose a recommended OpenAI model such as {recommended_openai_models_text()}."
                ),
                models=models,
                capabilities=capabilities,
            )

    def generate_structured_output(
        self,
        request: StructuredCompletionRequest,
    ) -> StructuredCompletionResult:
        return self._run_structured_completion(request)
