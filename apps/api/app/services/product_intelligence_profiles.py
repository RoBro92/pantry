from __future__ import annotations

from dataclasses import dataclass

from app.domain.ai import (
    AI_PROVIDER_CLAUDE,
    AI_PROVIDER_GEMINI,
    AI_PROVIDER_OLLAMA,
    AI_PROVIDER_OPENAI,
    canonical_provider_type,
)
from app.services.ai_providers.openai_compat import normalize_openai_model_id, resolve_supported_openai_model

PROFILE_TUNED = "supported"
PROFILE_STANDARD = "provider_default"
PROFILE_SAFE_FALLBACK = "safe_fallback"


@dataclass(frozen=True)
class RetryProfile:
    max_attempts: int
    initial_delay_seconds: float
    max_delay_seconds: float
    multiplier: float
    jitter_ratio: float = 0.2
    cooldown_after_exhausted_seconds: float = 8.0
    consecutive_failure_abort_threshold: int = 2


@dataclass(frozen=True)
class ProductIntelligenceExecutionProfile:
    provider_type: str
    profile_label: str
    support_level: str
    max_input_tokens: int
    max_output_tokens: int
    per_product_output_tokens: int
    max_products_per_batch: int
    request_timeout_seconds: float
    pause_between_batches_seconds: float
    retry: RetryProfile


@dataclass(frozen=True)
class SupportedModelProfile:
    model: str
    tier: str
    title: str
    description: str
    execution_profile: ProductIntelligenceExecutionProfile


GENERIC_FALLBACK_PROFILE = ProductIntelligenceExecutionProfile(
    provider_type="generic",
    profile_label="generic_safe_fallback",
    support_level=PROFILE_SAFE_FALLBACK,
    max_input_tokens=5_500,
    max_output_tokens=1_400,
    per_product_output_tokens=180,
    max_products_per_batch=4,
    request_timeout_seconds=60.0,
    pause_between_batches_seconds=1.5,
    retry=RetryProfile(
        max_attempts=3,
        initial_delay_seconds=1.5,
        max_delay_seconds=12.0,
        multiplier=2.0,
        cooldown_after_exhausted_seconds=12.0,
    ),
)

PROVIDER_FALLBACK_PROFILES: dict[str, ProductIntelligenceExecutionProfile] = {
    AI_PROVIDER_OPENAI: ProductIntelligenceExecutionProfile(
        provider_type=AI_PROVIDER_OPENAI,
        profile_label="openai_standard",
        support_level=PROFILE_STANDARD,
        max_input_tokens=8_500,
        max_output_tokens=1_800,
        per_product_output_tokens=170,
        max_products_per_batch=6,
        request_timeout_seconds=70.0,
        pause_between_batches_seconds=0.5,
        retry=RetryProfile(
            max_attempts=4,
            initial_delay_seconds=1.0,
            max_delay_seconds=10.0,
            multiplier=2.0,
        ),
    ),
    AI_PROVIDER_CLAUDE: ProductIntelligenceExecutionProfile(
        provider_type=AI_PROVIDER_CLAUDE,
        profile_label="claude_standard",
        support_level=PROFILE_STANDARD,
        max_input_tokens=10_000,
        max_output_tokens=2_000,
        per_product_output_tokens=180,
        max_products_per_batch=7,
        request_timeout_seconds=75.0,
        pause_between_batches_seconds=0.4,
        retry=RetryProfile(
            max_attempts=4,
            initial_delay_seconds=1.2,
            max_delay_seconds=12.0,
            multiplier=2.0,
        ),
    ),
    AI_PROVIDER_GEMINI: ProductIntelligenceExecutionProfile(
        provider_type=AI_PROVIDER_GEMINI,
        profile_label="gemini_standard",
        support_level=PROFILE_STANDARD,
        max_input_tokens=6_500,
        max_output_tokens=1_500,
        per_product_output_tokens=170,
        max_products_per_batch=5,
        request_timeout_seconds=75.0,
        pause_between_batches_seconds=2.0,
        retry=RetryProfile(
            max_attempts=5,
            initial_delay_seconds=2.0,
            max_delay_seconds=24.0,
            multiplier=2.0,
            cooldown_after_exhausted_seconds=18.0,
            consecutive_failure_abort_threshold=2,
        ),
    ),
    AI_PROVIDER_OLLAMA: ProductIntelligenceExecutionProfile(
        provider_type=AI_PROVIDER_OLLAMA,
        profile_label="ollama_standard",
        support_level=PROFILE_STANDARD,
        max_input_tokens=5_000,
        max_output_tokens=1_300,
        per_product_output_tokens=180,
        max_products_per_batch=3,
        request_timeout_seconds=120.0,
        pause_between_batches_seconds=0.0,
        retry=RetryProfile(
            max_attempts=3,
            initial_delay_seconds=1.0,
            max_delay_seconds=8.0,
            multiplier=2.0,
        ),
    ),
}

SUPPORTED_MODEL_PROFILES: dict[str, tuple[SupportedModelProfile, ...]] = {
    AI_PROVIDER_OPENAI: (
        SupportedModelProfile(
            model="gpt-4.1-mini",
            tier="lower",
            title="Fast / cheapest",
            description="The lowest-cost supported OpenAI option for compact Pantry AI runs.",
            execution_profile=ProductIntelligenceExecutionProfile(
                **{
                    **PROVIDER_FALLBACK_PROFILES[AI_PROVIDER_OPENAI].__dict__,
                    "profile_label": "openai_gpt_4_1_mini",
                    "support_level": PROFILE_TUNED,
                    "max_input_tokens": 8_000,
                    "max_products_per_batch": 5,
                }
            ),
        ),
        SupportedModelProfile(
            model="gpt-5.4-mini",
            tier="balanced",
            title="Balanced default",
            description="Pantry's recommended OpenAI default for product intelligence and meal suggestions.",
            execution_profile=ProductIntelligenceExecutionProfile(
                **{
                    **PROVIDER_FALLBACK_PROFILES[AI_PROVIDER_OPENAI].__dict__,
                    "profile_label": "openai_gpt_5_4_mini",
                    "support_level": PROFILE_TUNED,
                    "max_input_tokens": 9_000,
                    "max_products_per_batch": 7,
                }
            ),
        ),
        SupportedModelProfile(
            model="gpt-5.4",
            tier="higher",
            title="Higher quality",
            description="Use when Pantry should prioritize stronger OpenAI quality over latency and cost.",
            execution_profile=ProductIntelligenceExecutionProfile(
                **{
                    **PROVIDER_FALLBACK_PROFILES[AI_PROVIDER_OPENAI].__dict__,
                    "profile_label": "openai_gpt_5_4",
                    "support_level": PROFILE_TUNED,
                    "max_input_tokens": 10_000,
                    "max_output_tokens": 2_200,
                    "max_products_per_batch": 8,
                    "request_timeout_seconds": 85.0,
                }
            ),
        ),
    ),
    AI_PROVIDER_CLAUDE: (
        SupportedModelProfile(
            model="claude-haiku-4-5",
            tier="lower",
            title="Fast / lower cost",
            description="Anthropic’s fastest recommended Pantry option for compact structured work.",
            execution_profile=ProductIntelligenceExecutionProfile(
                **{
                    **PROVIDER_FALLBACK_PROFILES[AI_PROVIDER_CLAUDE].__dict__,
                    "profile_label": "claude_haiku_4_5",
                    "support_level": PROFILE_TUNED,
                    "max_input_tokens": 8_500,
                    "max_products_per_batch": 5,
                }
            ),
        ),
        SupportedModelProfile(
            model="claude-sonnet-4-6",
            tier="balanced",
            title="Balanced default",
            description="The default Anthropic pick for Pantry’s mixed quality and responsiveness needs.",
            execution_profile=ProductIntelligenceExecutionProfile(
                **{
                    **PROVIDER_FALLBACK_PROFILES[AI_PROVIDER_CLAUDE].__dict__,
                    "profile_label": "claude_sonnet_4_6",
                    "support_level": PROFILE_TUNED,
                    "max_input_tokens": 11_000,
                    "max_output_tokens": 2_200,
                    "max_products_per_batch": 8,
                    "request_timeout_seconds": 90.0,
                }
            ),
        ),
        SupportedModelProfile(
            model="claude-opus-4-6",
            tier="higher",
            title="Higher quality",
            description="Use when Pantry should favour quality over latency and cost.",
            execution_profile=ProductIntelligenceExecutionProfile(
                **{
                    **PROVIDER_FALLBACK_PROFILES[AI_PROVIDER_CLAUDE].__dict__,
                    "profile_label": "claude_opus_4_6",
                    "support_level": PROFILE_TUNED,
                    "max_input_tokens": 12_000,
                    "max_output_tokens": 2_400,
                    "max_products_per_batch": 8,
                    "request_timeout_seconds": 105.0,
                }
            ),
        ),
    ),
    AI_PROVIDER_GEMINI: (
        SupportedModelProfile(
            model="gemini-2.5-flash-lite",
            tier="lower",
            title="Fast / lower cost",
            description="The lightest Pantry-supported Gemini option.",
            execution_profile=ProductIntelligenceExecutionProfile(
                **{
                    **PROVIDER_FALLBACK_PROFILES[AI_PROVIDER_GEMINI].__dict__,
                    "profile_label": "gemini_2_5_flash_lite",
                    "support_level": PROFILE_TUNED,
                    "max_input_tokens": 5_500,
                    "max_products_per_batch": 4,
                    "pause_between_batches_seconds": 2.5,
                }
            ),
        ),
        SupportedModelProfile(
            model="gemini-2.5-flash",
            tier="balanced",
            title="Balanced default",
            description="The Pantry default Gemini model for classification and suggestion work.",
            execution_profile=ProductIntelligenceExecutionProfile(
                **{
                    **PROVIDER_FALLBACK_PROFILES[AI_PROVIDER_GEMINI].__dict__,
                    "profile_label": "gemini_2_5_flash",
                    "support_level": PROFILE_TUNED,
                    "max_input_tokens": 6_500,
                    "max_products_per_batch": 5,
                    "pause_between_batches_seconds": 2.0,
                }
            ),
        ),
        SupportedModelProfile(
            model="gemini-2.5-pro",
            tier="higher",
            title="Higher quality",
            description="Use when Pantry should favour stronger reasoning quality from Gemini.",
            execution_profile=ProductIntelligenceExecutionProfile(
                **{
                    **PROVIDER_FALLBACK_PROFILES[AI_PROVIDER_GEMINI].__dict__,
                    "profile_label": "gemini_2_5_pro",
                    "support_level": PROFILE_TUNED,
                    "max_input_tokens": 8_500,
                    "max_output_tokens": 1_900,
                    "max_products_per_batch": 6,
                    "request_timeout_seconds": 95.0,
                    "pause_between_batches_seconds": 2.5,
                }
            ),
        ),
    ),
    AI_PROVIDER_OLLAMA: (
        SupportedModelProfile(
            model="llama3.2",
            tier="lower",
            title="Fast / local",
            description="A practical local baseline if it is already installed.",
            execution_profile=ProductIntelligenceExecutionProfile(
                **{
                    **PROVIDER_FALLBACK_PROFILES[AI_PROVIDER_OLLAMA].__dict__,
                    "profile_label": "ollama_llama3_2",
                    "support_level": PROFILE_TUNED,
                    "max_input_tokens": 4_500,
                    "max_products_per_batch": 3,
                }
            ),
        ),
        SupportedModelProfile(
            model="qwen3:8b",
            tier="balanced",
            title="Balanced default",
            description="A strong local general-purpose default when available through Ollama.",
            execution_profile=ProductIntelligenceExecutionProfile(
                **{
                    **PROVIDER_FALLBACK_PROFILES[AI_PROVIDER_OLLAMA].__dict__,
                    "profile_label": "ollama_qwen3_8b",
                    "support_level": PROFILE_TUNED,
                    "max_input_tokens": 5_500,
                    "max_output_tokens": 1_500,
                    "max_products_per_batch": 4,
                }
            ),
        ),
        SupportedModelProfile(
            model="llama3.3",
            tier="higher",
            title="Higher quality",
            description="Use when a stronger local model is worth the extra latency.",
            execution_profile=ProductIntelligenceExecutionProfile(
                **{
                    **PROVIDER_FALLBACK_PROFILES[AI_PROVIDER_OLLAMA].__dict__,
                    "profile_label": "ollama_llama3_3",
                    "support_level": PROFILE_TUNED,
                    "max_input_tokens": 6_000,
                    "max_output_tokens": 1_700,
                    "max_products_per_batch": 4,
                    "request_timeout_seconds": 150.0,
                }
            ),
        ),
    ),
}


def get_supported_provider_models(provider_type: str) -> tuple[SupportedModelProfile, ...]:
    return SUPPORTED_MODEL_PROFILES.get(canonical_provider_type(provider_type) or "", ())


def get_default_supported_model(provider_type: str) -> str | None:
    for model in get_supported_provider_models(provider_type):
        if model.tier == "balanced":
            return model.model
    return None


def _normalize_model_id(value: str | None) -> str:
    return (value or "").strip().lower()


def _matches_supported_model(candidate: str, supported_model: str, *, provider_type: str | None = None) -> bool:
    normalized_provider = canonical_provider_type(provider_type)
    if normalized_provider == AI_PROVIDER_OPENAI:
        resolved = resolve_supported_openai_model(candidate)
        return resolved == normalize_openai_model_id(supported_model)

    normalized_candidate = _normalize_model_id(candidate)
    normalized_supported = _normalize_model_id(supported_model)
    if not normalized_candidate or not normalized_supported:
        return False
    if normalized_candidate == normalized_supported:
        return True
    if normalized_candidate.startswith(f"{normalized_supported}:"):
        return True
    return normalized_supported in normalized_candidate


def resolve_product_intelligence_profile(
    provider_type: str,
    model: str | None,
) -> ProductIntelligenceExecutionProfile:
    canonical_provider = canonical_provider_type(provider_type)
    if canonical_provider is None:
        return GENERIC_FALLBACK_PROFILE

    for supported in get_supported_provider_models(canonical_provider):
        if _matches_supported_model(model or "", supported.model, provider_type=canonical_provider):
            return supported.execution_profile

    return PROVIDER_FALLBACK_PROFILES.get(canonical_provider, GENERIC_FALLBACK_PROFILE)
