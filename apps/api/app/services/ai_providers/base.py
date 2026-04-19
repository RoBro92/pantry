from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AIProviderRuntimeConfig:
    provider_type: str
    base_url: str
    default_model: str
    api_key: str | None
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class AIProviderHealth:
    is_healthy: bool
    status: str
    message: str | None
    models: list[str]
    capabilities: dict[str, object]


@dataclass(frozen=True)
class StructuredCompletionRequest:
    model: str
    system_prompt: str
    user_payload: dict[str, Any]
    output_schema: dict[str, Any]
    temperature: float = 0.2
    schema_name: str = "pantry_ai_response"
    max_output_tokens: int | None = None
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class AIUsageMetrics:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    @property
    def has_values(self) -> bool:
        return any(value is not None for value in (self.input_tokens, self.output_tokens, self.total_tokens))


@dataclass(frozen=True)
class StructuredCompletionResult:
    output_text: str
    parsed_output: dict[str, Any]
    provider_request_id: str | None
    usage: AIUsageMetrics | None = None


class AIProviderAdapter(Protocol):
    def check_health(self) -> AIProviderHealth:
        ...

    def list_models(self) -> list[str]:
        ...

    def generate_structured_output(
        self,
        request: StructuredCompletionRequest,
    ) -> StructuredCompletionResult:
        ...
