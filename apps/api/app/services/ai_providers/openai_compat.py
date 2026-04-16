from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

import httpx

from app.services.ai_providers.errors import AIProviderError, OpenAISchemaCompatibilityError

OPENAI_PROFILED_MODEL_PREFIXES = (
    "gpt-4.1",
    "gpt-5",
    "o3-mini",
    "o4-mini",
)
OPENAI_RECOMMENDED_MODELS = ("gpt-4.1-mini", "gpt-5.4-mini", "gpt-5.4")
_OPENAI_SUPPORTED_MODEL_MATCH_ORDER = tuple(
    sorted(OPENAI_RECOMMENDED_MODELS, key=len, reverse=True)
)
_OPENAI_MODEL_NAMESPACE_PREFIXES = ("models/", "openai/")
_OPENAI_VERSION_SUFFIX = re.compile(r"^(?P<base>.+?)(?:[-:](?:latest|preview|[0-9]{4}.*))$")

_OPENAI_UNSUPPORTED_VALIDATION_KEYS = {
    "default",
    "description",
    "examples",
    "format",
    "maxItems",
    "maxLength",
    "maxProperties",
    "maximum",
    "minItems",
    "minLength",
    "minProperties",
    "minimum",
    "multipleOf",
    "pattern",
    "title",
}


def normalize_openai_model_id(model: str | None) -> str:
    normalized = (model or "").strip().casefold()
    for prefix in _OPENAI_MODEL_NAMESPACE_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    return normalized


def canonicalize_openai_model_id(model: str | None) -> str:
    normalized = normalize_openai_model_id(model)
    return resolve_supported_openai_model(normalized) or normalized


def resolve_supported_openai_model(model: str | None) -> str | None:
    normalized = normalize_openai_model_id(model)
    if not normalized:
        return None
    for supported in _OPENAI_SUPPORTED_MODEL_MATCH_ORDER:
        if normalized == supported:
            return supported
        if normalized.startswith(f"{supported}:"):
            return supported
        if normalized.startswith(f"{supported}-"):
            suffix = normalized[len(supported) + 1 :]
            if suffix and (suffix[:1].isdigit() or suffix.startswith("latest") or suffix.startswith("preview")):
                return supported
    version_match = _OPENAI_VERSION_SUFFIX.match(normalized)
    if version_match is not None:
        return resolve_supported_openai_model(version_match.group("base"))
    return None


def is_supported_openai_model(model: str | None) -> bool:
    return resolve_supported_openai_model(model) is not None


def describe_openai_model(model: str | None) -> str:
    return resolve_supported_openai_model(model) or canonicalize_openai_model_id(model) or "unknown"


def normalize_openai_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    copied = deepcopy(schema)
    normalized = _normalize_schema_node(copied)
    if not isinstance(normalized, dict):
        raise OpenAISchemaCompatibilityError("OpenAI structured output schema must normalize to an object.")
    return normalized


def openai_model_profile(model: str) -> str:
    normalized = canonicalize_openai_model_id(model)
    if normalized.startswith(OPENAI_PROFILED_MODEL_PREFIXES):
        return "profiled"
    return "unprofiled"


def recommended_openai_models_text() -> str:
    return ", ".join(OPENAI_RECOMMENDED_MODELS)


def openai_completion_token_param(model: str | None) -> str:
    normalized = canonicalize_openai_model_id(model)
    if normalized.startswith(("gpt-5", "o3", "o4")):
        return "max_completion_tokens"
    return "max_tokens"


def build_openai_supported_model_failure_message(model: str | None) -> str:
    model_name = describe_openai_model(model)
    return (
        f"Pantry could not complete a structured AI request with the OpenAI model '{model_name}'. "
        "Re-run the health check and try again. "
        f"If it still fails, switch to another Pantry-supported OpenAI model: {recommended_openai_models_text()}."
    )


def build_openai_unsupported_model_message(model: str | None) -> str:
    model_name = describe_openai_model(model)
    return (
        f"The OpenAI model '{model_name}' is not a good fit for Pantry's structured AI workflow. "
        f"Use one of Pantry's supported OpenAI models: {recommended_openai_models_text()}."
    )


def extract_openai_message_text(message: dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") in {"text", "output_text"}
        )
    return ""


def extract_openai_refusal(message: dict[str, Any]) -> str | None:
    refusal = message.get("refusal")
    if isinstance(refusal, str) and refusal.strip():
        return refusal.strip()
    if isinstance(refusal, list):
        combined = "".join(
            str(part.get("text", ""))
            for part in refusal
            if isinstance(part, dict) and part.get("type") in {"text", "output_text"}
        ).strip()
        return combined or None
    return None


def map_openai_http_error(exc: httpx.HTTPStatusError, *, model: str) -> AIProviderError:
    response = exc.response
    status_code = response.status_code
    provider_message = _extract_openai_error_message(response)
    lowered = provider_message.casefold()
    recommended_models = recommended_openai_models_text()

    if status_code in {401, 403}:
        return AIProviderError(
            "OpenAI rejected the configured credentials. Check the API key and project access.",
            diagnostic_message=provider_message,
            category="invalid_configuration",
        )
    if status_code == 429:
        return AIProviderError(
            "OpenAI rate limits are currently preventing Pantry AI requests. Try again shortly.",
            diagnostic_message=provider_message,
            category="rate_limited",
        )
    if status_code >= 500:
        return AIProviderError(
            "OpenAI is temporarily unavailable. Try again in a moment.",
            diagnostic_message=provider_message,
            category="upstream_unavailable",
        )
    if status_code == 400 and any(
        token in lowered
        for token in (
            "json_schema",
            "response_format",
            "structured output",
            "structured outputs",
            "invalid schema",
            "schema",
            "not supported",
            "unsupported",
        )
    ):
        if is_supported_openai_model(model):
            return AIProviderError(
                build_openai_supported_model_failure_message(model),
                diagnostic_message=provider_message,
                category="invalid_request",
            )
        return AIProviderError(
            build_openai_unsupported_model_message(model),
            diagnostic_message=provider_message,
            category="unsupported_model",
        )
    if status_code == 400:
        return AIProviderError(
            (
                build_openai_supported_model_failure_message(model)
                if is_supported_openai_model(model)
                else (
                    "OpenAI rejected Pantry's structured AI request. "
                    f"Re-run the health check or choose a recommended OpenAI model such as {recommended_models}."
                )
            ),
            diagnostic_message=provider_message,
            category="invalid_request",
        )
    return AIProviderError(
        "Pantry could not complete the OpenAI request.",
        diagnostic_message=provider_message,
        category="provider_error",
    )


def map_openai_transport_error(exc: httpx.HTTPError) -> AIProviderError:
    return AIProviderError(
        "Pantry could not reach OpenAI. Check the base URL, network access, and firewall settings.",
        diagnostic_message=str(exc),
        category="network_error",
    )


def _normalize_schema_node(schema: Any) -> Any:
    if isinstance(schema, bool):
        return schema
    if not isinstance(schema, dict):
        raise OpenAISchemaCompatibilityError("OpenAI structured output schema nodes must be objects.")

    if "$ref" in schema:
        return {"$ref": schema["$ref"]}

    if "oneOf" in schema:
        return {"anyOf": [_normalize_schema_node(option) for option in schema["oneOf"]]}

    if "allOf" in schema:
        options = schema["allOf"]
        if not isinstance(options, list) or len(options) != 1:
            raise OpenAISchemaCompatibilityError("OpenAI schema normalization only supports single-branch allOf.")
        return _normalize_schema_node(options[0])

    if "anyOf" in schema:
        normalized_options = [_normalize_schema_node(option) for option in schema["anyOf"]]
        collapsed = _collapse_nullable_anyof(normalized_options)
        return collapsed if collapsed is not None else {"anyOf": normalized_options}

    schema_type = schema.get("type")
    if schema_type == "object" or "properties" in schema:
        return _normalize_object_schema(schema)
    if schema_type == "array":
        normalized = {"type": "array"}
        if "items" in schema:
            normalized["items"] = _normalize_schema_node(schema["items"])
        return _copy_supported_scalar_keywords(schema, normalized)
    if isinstance(schema_type, list):
        normalized = {"type": list(schema_type)}
        return _copy_supported_scalar_keywords(schema, normalized)
    if schema_type is not None:
        normalized = {"type": schema_type}
        return _copy_supported_scalar_keywords(schema, normalized)

    if "$defs" in schema:
        normalized = _copy_supported_scalar_keywords(schema, {})
        normalized["$defs"] = {
            key: _normalize_schema_node(value)
            for key, value in schema["$defs"].items()
        }
        return normalized

    raise OpenAISchemaCompatibilityError("Encountered an unsupported OpenAI schema node.")


def _normalize_object_schema(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties") or {}
    if not isinstance(properties, dict):
        raise OpenAISchemaCompatibilityError("Object schema properties must be a mapping.")

    original_required = {
        key
        for key in schema.get("required", [])
        if isinstance(key, str)
    }
    normalized_properties: dict[str, Any] = {}
    for key, value in properties.items():
        normalized_value = _normalize_schema_node(value)
        if key not in original_required:
            normalized_value = _make_nullable(normalized_value)
        normalized_properties[key] = normalized_value

    normalized: dict[str, Any] = {
        "type": "object",
        "properties": normalized_properties,
        "required": list(normalized_properties.keys()),
        "additionalProperties": False,
    }
    if "$defs" in schema and isinstance(schema["$defs"], dict):
        normalized["$defs"] = {
            key: _normalize_schema_node(value)
            for key, value in schema["$defs"].items()
        }
    return _copy_supported_scalar_keywords(schema, normalized)


def _make_nullable(schema: Any) -> Any:
    if isinstance(schema, bool):
        return schema
    if not isinstance(schema, dict):
        raise OpenAISchemaCompatibilityError("Nullable schema nodes must be objects.")

    if "$ref" in schema:
        return {"anyOf": [schema, {"type": "null"}]}

    schema_type = schema.get("type")
    if isinstance(schema_type, str):
        nullable = dict(schema)
        nullable["type"] = [schema_type, "null"]
        return nullable
    if isinstance(schema_type, list):
        if "null" in schema_type:
            return schema
        nullable = dict(schema)
        nullable["type"] = [*schema_type, "null"]
        return nullable
    if "anyOf" in schema:
        options = list(schema["anyOf"])
        if not any(isinstance(option, dict) and option.get("type") == "null" for option in options):
            options.append({"type": "null"})
        return {"anyOf": options}
    return {"anyOf": [schema, {"type": "null"}]}


def _collapse_nullable_anyof(options: list[Any]) -> dict[str, Any] | None:
    if len(options) != 2:
        return None

    null_options = [option for option in options if isinstance(option, dict) and option.get("type") == "null"]
    non_null_options = [option for option in options if option not in null_options]
    if len(null_options) != 1 or len(non_null_options) != 1:
        return None

    option = non_null_options[0]
    if not isinstance(option, dict) or "$ref" in option:
        return None
    option_type = option.get("type")
    if not isinstance(option_type, str):
        return None

    collapsed = dict(option)
    collapsed["type"] = [option_type, "null"]
    return collapsed


def _copy_supported_scalar_keywords(source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    for key, value in source.items():
        if key in _OPENAI_UNSUPPORTED_VALIDATION_KEYS:
            continue
        if key in {"properties", "required", "additionalProperties", "items", "$defs", "oneOf", "allOf", "anyOf"}:
            continue
        target[key] = value
    return target


def _extract_openai_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text or f"OpenAI request failed with status {response.status_code}."

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
    text = response.text.strip()
    return text or f"OpenAI request failed with status {response.status_code}."
