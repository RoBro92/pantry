from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import ValidationError

from app.domain.ai import AI_PROVIDER_OPENAI, canonical_provider_type
from app.services.ai_providers.errors import AIProviderError
from app.services.ai_providers.openai_compat import (
    build_openai_supported_model_failure_message,
    build_openai_unsupported_model_message,
    describe_openai_model,
    is_supported_openai_model,
    recommended_openai_models_text,
)

OPENAI_SUPPORTED_MODELS = ("gpt-4.1-mini", "gpt-5.4-mini", "gpt-5.4")
TRANSIENT_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}

AI_ERROR_CONFIGURATION = "configuration"
AI_ERROR_UNSUPPORTED_PROVIDER = "unsupported_provider"
AI_ERROR_UNSUPPORTED_MODEL = "unsupported_model"
AI_ERROR_RATE_LIMIT = "rate_limit"
AI_ERROR_INVALID_RESPONSE = "invalid_response"
AI_ERROR_TEMPORARY_UPSTREAM = "temporary_upstream"
AI_ERROR_REQUEST_FAILED = "request_failed"


@dataclass(frozen=True)
class PantryAIError(ValueError):
    category: str
    technical_message: str
    retryable: bool = False
    status_code: int = 503

    def __init__(
        self,
        user_message: str,
        *,
        category: str,
        technical_message: str,
        retryable: bool = False,
        status_code: int = 503,
    ):
        super().__init__(user_message)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "technical_message", technical_message)
        object.__setattr__(self, "retryable", retryable)
        object.__setattr__(self, "status_code", status_code)


def get_provider_support_copy(provider_type: str | None) -> str:
    provider = canonical_provider_type(provider_type)
    if provider == AI_PROVIDER_OPENAI:
        return f"Use one of Pantro's supported OpenAI models: {recommended_openai_models_text()}."
    return "Pantro currently supports OpenAI for product classification and guided meal suggestions."


def normalize_ai_error(
    error: Exception | str,
    *,
    provider_type: str | None = None,
    model: str | None = None,
) -> PantryAIError:
    if isinstance(error, PantryAIError):
        return error

    technical_message = _extract_technical_message(error)
    normalized_provider = canonical_provider_type(provider_type)
    lower_message = technical_message.lower()

    if isinstance(error, AIProviderError):
        if error.category == "unsupported_model":
            return PantryAIError(
                error.user_message,
                category=AI_ERROR_UNSUPPORTED_MODEL,
                technical_message=error.diagnostic_message,
            )
        if error.category == "rate_limited":
            return PantryAIError(
                error.user_message,
                category=AI_ERROR_RATE_LIMIT,
                technical_message=error.diagnostic_message,
                retryable=True,
            )
        if error.category == "invalid_configuration":
            return PantryAIError(
                error.user_message,
                category=AI_ERROR_CONFIGURATION,
                technical_message=error.diagnostic_message,
            )
        if error.category in {"upstream_unavailable", "network_error"}:
            return PantryAIError(
                error.user_message,
                category=AI_ERROR_TEMPORARY_UPSTREAM,
                technical_message=error.diagnostic_message,
                retryable=True,
            )
        if error.category == "invalid_response":
            return PantryAIError(
                error.user_message,
                category=AI_ERROR_INVALID_RESPONSE,
                technical_message=error.diagnostic_message,
            )
        return PantryAIError(
            error.user_message,
            category=AI_ERROR_REQUEST_FAILED,
            technical_message=error.diagnostic_message,
        )

    if normalized_provider and normalized_provider != AI_PROVIDER_OPENAI and any(
        token in lower_message for token in ("not currently supported", "foundation only")
    ):
        return PantryAIError(
            "Pantro currently supports OpenAI for product classification and guided meal suggestions.",
            category=AI_ERROR_UNSUPPORTED_PROVIDER,
            technical_message=technical_message,
        )

    if isinstance(error, AIProviderError):
        return _normalize_provider_error(error)

    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code if error.response is not None else None
        response_text = _extract_response_text(error.response)
        combined = " ".join(part for part in (technical_message, response_text) if part).lower()

        if status_code == 429:
            return PantryAIError(
                "The AI provider is rate limiting Pantro right now. Wait a moment and retry.",
                category=AI_ERROR_RATE_LIMIT,
                technical_message=technical_message,
                retryable=True,
            )
        if status_code in {401, 403}:
            return PantryAIError(
                "Pantro could not authenticate with the AI provider. Check the API key and base URL in AI settings.",
                category=AI_ERROR_CONFIGURATION,
                technical_message=technical_message,
            )
        if status_code == 404 and any(token in combined for token in ("model", "not found", "does not exist")):
            if normalized_provider == AI_PROVIDER_OPENAI and is_supported_openai_model(model):
                return PantryAIError(
                    (
                        f"The configured OpenAI account could not access the model "
                        f"'{describe_openai_model(model)}'. Confirm model access, or use another "
                        f"Pantro-supported OpenAI model: {recommended_openai_models_text()}."
                    ),
                    category=AI_ERROR_CONFIGURATION,
                    technical_message=technical_message,
                )
            return PantryAIError(
                _unsupported_model_message(normalized_provider, model),
                category=AI_ERROR_UNSUPPORTED_MODEL,
                technical_message=technical_message,
            )
        if status_code == 400 and _looks_like_output_token_parameter_error(combined):
            return PantryAIError(
                "The AI provider rejected Pantro's structured request parameters. Retry, or re-run the health check after changing models.",
                category=AI_ERROR_REQUEST_FAILED,
                technical_message=technical_message,
            )
        if status_code == 400 and any(
            token in combined
            for token in (
                "json_schema",
                "response_format",
                "invalid schema",
                "schema",
                "structured output",
                "strict",
            )
        ):
            if normalized_provider == AI_PROVIDER_OPENAI and is_supported_openai_model(model):
                return PantryAIError(
                    build_openai_supported_model_failure_message(model),
                    category=AI_ERROR_REQUEST_FAILED,
                    technical_message=technical_message,
                )
            return PantryAIError(
                _unsupported_model_message(normalized_provider, model),
                category=AI_ERROR_UNSUPPORTED_MODEL,
                technical_message=technical_message,
            )
        if status_code in TRANSIENT_STATUS_CODES:
            return PantryAIError(
                "The AI provider is temporarily unavailable. Retry in a moment.",
                category=AI_ERROR_TEMPORARY_UPSTREAM,
                technical_message=technical_message,
                retryable=True,
            )
        return PantryAIError(
            "Pantro could not complete the AI request. Review the AI provider settings and try again.",
            category=AI_ERROR_REQUEST_FAILED,
            technical_message=technical_message,
        )

    if isinstance(error, (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError)):
        return PantryAIError(
            "The AI provider is temporarily unavailable. Retry in a moment.",
            category=AI_ERROR_TEMPORARY_UPSTREAM,
            technical_message=technical_message,
            retryable=True,
        )

    if isinstance(error, (json.JSONDecodeError, ValidationError)):
        return PantryAIError(
            "The AI provider returned a response Pantro could not use. Retry, or switch to a supported OpenAI model.",
            category=AI_ERROR_INVALID_RESPONSE,
            technical_message=technical_message,
        )

    if any(token in lower_message for token in ("timed out", "timeout", "temporarily unavailable", "connection reset")):
        return PantryAIError(
            "The AI provider is temporarily unavailable. Retry in a moment.",
            category=AI_ERROR_TEMPORARY_UPSTREAM,
            technical_message=technical_message,
            retryable=True,
        )

    if any(token in lower_message for token in ("empty response", "provider returned an empty response", "did not return")):
        return PantryAIError(
            "The AI provider returned a response Pantro could not use. Retry, or switch to a supported OpenAI model.",
            category=AI_ERROR_INVALID_RESPONSE,
            technical_message=technical_message,
        )

    if any(token in lower_message for token in ("api key", "authentication", "unauthorized", "forbidden")):
        return PantryAIError(
            "Pantro could not authenticate with the AI provider. Check the API key and base URL in AI settings.",
            category=AI_ERROR_CONFIGURATION,
            technical_message=technical_message,
        )

    if _looks_like_output_token_parameter_error(lower_message):
        return PantryAIError(
            "The AI provider rejected Pantro's structured request parameters. Retry, or re-run the health check after changing models.",
            category=AI_ERROR_REQUEST_FAILED,
            technical_message=technical_message,
        )

    if normalized_provider == AI_PROVIDER_OPENAI and is_supported_openai_model(model) and any(
        token in lower_message
        for token in (
            "structured ai workflow",
            "structured ai request",
            "structured ai requests",
            "structured output",
            "not compatible with pantry",
            "not a good fit",
            "does not support",
        )
    ):
        return PantryAIError(
            build_openai_supported_model_failure_message(model),
            category=AI_ERROR_REQUEST_FAILED,
            technical_message=technical_message,
        )

    if any(token in lower_message for token in ("unsupported model", "model not found", "model does not exist")):
        return PantryAIError(
            _unsupported_model_message(normalized_provider, model),
            category=AI_ERROR_UNSUPPORTED_MODEL,
            technical_message=technical_message,
        )

    return PantryAIError(
        "Pantro could not complete the AI request. Review the AI provider settings and try again.",
        category=AI_ERROR_REQUEST_FAILED,
        technical_message=technical_message,
    )


def _extract_technical_message(error: Exception | str) -> str:
    if isinstance(error, str):
        return error
    if isinstance(error, httpx.HTTPStatusError):
        response_text = _extract_response_text(error.response)
        if response_text:
            return f"{error} {response_text}"
    return str(error)


def _extract_response_text(response: httpx.Response | None) -> str:
    if response is None:
        return ""
    text = response.text.strip()
    return text[:500]


def _normalize_provider_error(error: AIProviderError) -> PantryAIError:
    if error.category == "invalid_configuration":
        return PantryAIError(
            str(error),
            category=AI_ERROR_CONFIGURATION,
            technical_message=error.diagnostic_message,
        )
    if error.category == "unsupported_model":
        return PantryAIError(
            str(error),
            category=AI_ERROR_UNSUPPORTED_MODEL,
            technical_message=error.diagnostic_message,
        )
    if error.category == "rate_limited":
        return PantryAIError(
            str(error),
            category=AI_ERROR_RATE_LIMIT,
            technical_message=error.diagnostic_message,
            retryable=True,
        )
    if error.category in {"network_error", "upstream_unavailable"}:
        return PantryAIError(
            str(error),
            category=AI_ERROR_TEMPORARY_UPSTREAM,
            technical_message=error.diagnostic_message,
            retryable=True,
        )
    if error.category == "invalid_response":
        return PantryAIError(
            str(error),
            category=AI_ERROR_INVALID_RESPONSE,
            technical_message=error.diagnostic_message,
        )
    return PantryAIError(
        str(error),
        category=AI_ERROR_REQUEST_FAILED,
        technical_message=error.diagnostic_message,
    )


def _looks_like_output_token_parameter_error(message: str) -> bool:
    return (
        ("unsupported parameter" in message or "unsupported_parameter" in message)
        and ("max_tokens" in message or "max_completion_tokens" in message)
    )


def _unsupported_model_message(provider_type: str | None, model: str | None) -> str:
    provider_hint = get_provider_support_copy(provider_type)
    if provider_type == AI_PROVIDER_OPENAI and model:
        return build_openai_unsupported_model_message(model)
    return f"This AI model/provider combination is not currently supported for Pantro's structured AI workflow. {provider_hint}"
