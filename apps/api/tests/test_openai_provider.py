from __future__ import annotations

import httpx
import pytest

from app.services.ai_providers import AIProviderRuntimeConfig, StructuredCompletionRequest
from app.services.ai_providers.openai import OpenAIProviderAdapter
from app.services.ai_providers.openai_compat import (
    canonicalize_openai_model_id,
    normalize_openai_json_schema,
    resolve_supported_openai_model,
)
from app.services.product_intelligence import ProductClassificationOutput
from app.schemas.ai import AIProviderMealSuggestionOutput


FORBIDDEN_SCHEMA_KEYS = {
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


class FakeHTTPXClient:
    def __init__(self, handler, *args, **kwargs):
        self._handler = handler

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def request(self, method, url, json=None):
        return self._handler(method, url, json)


def _runtime_config(*, model: str = "gpt-5.4-mini") -> AIProviderRuntimeConfig:
    return AIProviderRuntimeConfig(
        provider_type="openai",
        base_url="https://api.openai.com/v1",
        default_model=model,
        api_key="test-openai-key",
    )


def _json_response(method: str, url: str, payload: dict) -> httpx.Response:
    return httpx.Response(200, request=httpx.Request(method, url), json=payload)


def _error_response(method: str, url: str, status_code: int, payload: dict) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request(method, url), json=payload)


def _assert_strict_openai_schema(node):
    if isinstance(node, dict):
        is_schema_node = bool(
            {"type", "$ref", "anyOf", "properties", "items", "enum", "required", "additionalProperties"}
            & set(node.keys())
        )
        if is_schema_node:
            assert not (FORBIDDEN_SCHEMA_KEYS & set(node.keys()))
        if node.get("type") == "object":
            properties = node.get("properties", {})
            assert node.get("additionalProperties") is False
            assert sorted(node.get("required", [])) == sorted(properties.keys())
        for value in node.values():
            _assert_strict_openai_schema(value)
    elif isinstance(node, list):
        for item in node:
            _assert_strict_openai_schema(item)


def test_openai_schema_normalization_rewrites_product_and_meal_schemas_for_strict_mode():
    product_schema = normalize_openai_json_schema(ProductClassificationOutput.model_json_schema())
    meal_schema = normalize_openai_json_schema(AIProviderMealSuggestionOutput.model_json_schema())

    _assert_strict_openai_schema(product_schema)
    _assert_strict_openai_schema(meal_schema)

    assert product_schema["properties"]["confidence"]["type"] == ["number", "null"]
    assert sorted(product_schema["$defs"]["ProductClassificationMetadataPayload"]["required"]) == [
        "cuisine_tags",
        "flavour_tags",
        "preparation_tags",
        "product_format",
        "storage_profile",
    ]
    assert sorted(meal_schema["$defs"]["AIProviderMealSuggestionItem"]["required"]) == [
        "dietary_fit_summary",
        "ingredients",
        "short_summary",
        "source",
        "steps",
        "title",
        "total_time_minutes",
        "why_it_matches",
    ]


def test_openai_adapter_posts_compact_payload_and_normalized_schema_for_structured_requests(monkeypatch):
    captured: dict[str, object] = {}

    def handler(method, url, json_body):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = json_body
        return _json_response(
            method,
            url,
            {
                "id": "chatcmpl_test",
                "choices": [
                    {
                        "message": {
                            "content": '{"suggestions":[]}',
                        }
                    }
                ],
            },
        )

    monkeypatch.setattr(
        "app.services.ai_providers.openai.httpx.Client",
        lambda *args, **kwargs: FakeHTTPXClient(handler, *args, **kwargs),
    )

    adapter = OpenAIProviderAdapter(_runtime_config())
    result = adapter.generate_structured_output(
        StructuredCompletionRequest(
            model="gpt-5.4-mini",
            schema_name="pantry_meal_suggestion",
            system_prompt="Return valid JSON only.",
            user_payload={"request": {"pantry_only": True}, "context": {"items": ["pasta"]}},
            output_schema=AIProviderMealSuggestionOutput.model_json_schema(),
        )
    )

    assert result.parsed_output == {"suggestions": []}
    assert captured["method"] == "POST"
    assert str(captured["url"]).endswith("/chat/completions")

    payload = captured["json"]
    assert payload["messages"][1]["content"] == '{"request":{"pantry_only":true},"context":{"items":["pasta"]}}'
    assert payload["response_format"]["json_schema"]["name"] == "pantry_meal_suggestion"
    _assert_strict_openai_schema(payload["response_format"]["json_schema"]["schema"])


def test_openai_health_check_marks_provider_unhealthy_when_models_list_but_structured_probe_fails(monkeypatch):
    def handler(method, url, json_body):
        if url.endswith("/models"):
            return _json_response(
                method,
                url,
                {"data": [{"id": "gpt-4.1-mini"}, {"id": "gpt-5.4-mini"}, {"id": "gpt-5.4"}]},
            )
        return _error_response(
            method,
            url,
            400,
            {
                "error": {
                    "message": (
                        "Invalid schema for response_format 'json_schema': "
                        "In context=(), 'required' is required to be supplied and to be an array."
                    )
                }
            },
        )

    monkeypatch.setattr(
        "app.services.ai_providers.openai.httpx.Client",
        lambda *args, **kwargs: FakeHTTPXClient(handler, *args, **kwargs),
    )

    adapter = OpenAIProviderAdapter(_runtime_config(model="gpt-5.4-mini"))
    health = adapter.check_health()

    assert health.is_healthy is False
    assert health.models == ["gpt-4.1-mini", "gpt-5.4", "gpt-5.4-mini"]
    assert health.capabilities["recommended_models"] == ["gpt-4.1-mini", "gpt-5.4-mini", "gpt-5.4"]
    assert "could not complete a structured AI request" in (health.message or "")
    assert "gpt-5.4-mini" in (health.message or "")
    assert "400 Bad Request" not in (health.message or "")


def test_openai_health_check_allows_unprofiled_models_that_pass_the_compatibility_probe(monkeypatch):
    def handler(method, url, json_body):
        if url.endswith("/models"):
            return _json_response(method, url, {"data": [{"id": "custom-openai-model"}]})
        return _json_response(
            method,
            url,
            {
                "id": "chatcmpl_health",
                "choices": [
                    {
                        "message": {
                            "content": '{"status":"ok"}',
                        }
                    }
                ],
            },
        )

    monkeypatch.setattr(
        "app.services.ai_providers.openai.httpx.Client",
        lambda *args, **kwargs: FakeHTTPXClient(handler, *args, **kwargs),
    )

    adapter = OpenAIProviderAdapter(_runtime_config(model="custom-openai-model"))
    health = adapter.check_health()

    assert health.is_healthy is True
    assert health.capabilities["default_model_profile"] == "unprofiled"
    assert health.models == ["custom-openai-model"]


@pytest.mark.parametrize(
    ("raw_model", "expected_supported"),
    [
        (" gpt-4.1-mini ", "gpt-4.1-mini"),
        ("GPT-5.4-MINI", "gpt-5.4-mini"),
        ("gpt-5.4-preview", "gpt-5.4"),
        ("models/gpt-5.4-mini", "gpt-5.4-mini"),
        ("openai/gpt-5.4", "gpt-5.4"),
    ],
)
def test_openai_supported_model_resolution_normalizes_aliases(raw_model, expected_supported):
    assert resolve_supported_openai_model(raw_model) == expected_supported
    assert canonicalize_openai_model_id(raw_model) == expected_supported


def test_openai_adapter_parses_text_content_arrays(monkeypatch):
    def handler(method, url, json_body):
        return _json_response(
            method,
            url,
            {
                "id": "chatcmpl_array",
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": '{"suggestions":[]}'},
                            ]
                        }
                    }
                ],
            },
        )

    monkeypatch.setattr(
        "app.services.ai_providers.openai.httpx.Client",
        lambda *args, **kwargs: FakeHTTPXClient(handler, *args, **kwargs),
    )

    adapter = OpenAIProviderAdapter(_runtime_config())
    result = adapter.generate_structured_output(
        StructuredCompletionRequest(
            model="gpt-5.4-mini",
            system_prompt="Return valid JSON only.",
            user_payload={"task": "test"},
            output_schema=AIProviderMealSuggestionOutput.model_json_schema(),
        )
    )

    assert result.parsed_output == {"suggestions": []}
