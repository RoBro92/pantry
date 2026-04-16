from __future__ import annotations

import json

from app.services.ai_providers.base import AIProviderRuntimeConfig, StructuredCompletionRequest
from app.services.ai_providers.openai import OpenAIProviderAdapter
from app.services.product_intelligence import build_product_classification_batch_schema


class StubResponse:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def test_openai_adapter_sanitizes_strict_json_schema_before_request(monkeypatch):
    captured_payload: dict[str, object] = {}

    class StubClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, method: str, url: str, json: dict[str, object] | None = None):
            assert method == "POST"
            assert json is not None
            captured_payload.update(json)
            return StubResponse(
                {
                    "id": "resp_openai_123",
                    "choices": [
                        {
                            "message": {
                                "content": '{"items":[]}',
                            }
                        }
                    ],
                }
            )

    monkeypatch.setattr("app.services.ai_providers.openai.httpx.Client", StubClient)

    adapter = OpenAIProviderAdapter(
        AIProviderRuntimeConfig(
            provider_type="openai",
            base_url="https://api.openai.com/v1",
            default_model="gpt-4.1-mini",
            api_key="openai-test-key",
        )
    )

    result = adapter.generate_structured_output(
        StructuredCompletionRequest(
            model="gpt-4.1-mini",
            system_prompt="Return valid JSON only.",
            user_payload={"products": []},
            output_schema=build_product_classification_batch_schema(),
            max_output_tokens=800,
        )
    )

    assert result.parsed_output == {"items": []}
    schema = captured_payload["response_format"]["json_schema"]["schema"]  # type: ignore[index]
    assert schema["required"] == ["items"]  # type: ignore[index]
    item_schema = schema["properties"]["items"]["items"]  # type: ignore[index]
    assert set(item_schema["required"]) == set(item_schema["properties"].keys())  # type: ignore[index]
    assert "default" not in json.dumps(schema)
    assert "$defs" not in schema
