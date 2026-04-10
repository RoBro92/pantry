from __future__ import annotations

AI_SCOPE_INSTANCE = "instance"
AI_SCOPE_HOUSEHOLD = "household"
AI_SCOPE_KEY_INSTANCE = "instance"

AI_PROVIDER_OPENAI = "openai"
AI_PROVIDER_CLAUDE = "claude"
AI_PROVIDER_GEMINI = "gemini"
AI_PROVIDER_OLLAMA = "ollama"
AI_PROVIDER_OPENAI_COMPATIBLE = "openai_compatible"
AI_PROVIDER_ALIASES = {
    AI_PROVIDER_OPENAI_COMPATIBLE: AI_PROVIDER_OPENAI,
}
AI_PROVIDER_TYPES = {
    AI_PROVIDER_OPENAI,
    AI_PROVIDER_CLAUDE,
    AI_PROVIDER_GEMINI,
    AI_PROVIDER_OLLAMA,
}
AI_PROVIDER_DEFAULT_BASE_URLS = {
    AI_PROVIDER_OPENAI: "https://api.openai.com/v1",
    AI_PROVIDER_CLAUDE: "https://api.anthropic.com",
    AI_PROVIDER_GEMINI: "https://generativelanguage.googleapis.com",
    AI_PROVIDER_OLLAMA: "http://localhost:11434",
}
AI_PROVIDER_API_KEY_REQUIRED = {
    AI_PROVIDER_OPENAI: True,
    AI_PROVIDER_CLAUDE: True,
    AI_PROVIDER_GEMINI: True,
    AI_PROVIDER_OLLAMA: False,
}


def canonical_provider_type(provider_type: str | None) -> str | None:
    if provider_type is None:
        return None
    return AI_PROVIDER_ALIASES.get(provider_type, provider_type)

AI_HEALTH_UNKNOWN = "unknown"
AI_HEALTH_HEALTHY = "healthy"
AI_HEALTH_UNHEALTHY = "unhealthy"

AI_SUGGESTION_MEAL = "meal_suggestions"
AI_SUGGESTION_EXPIRY_FIRST = "expiry_first"
AI_SUGGESTION_BUY_EXTRA = "buy_a_few_extra"
AI_SUGGESTION_RECIPE_GAP = "recipe_gap"
AI_SUGGESTION_KINDS = {
    AI_SUGGESTION_MEAL,
    AI_SUGGESTION_EXPIRY_FIRST,
    AI_SUGGESTION_BUY_EXTRA,
    AI_SUGGESTION_RECIPE_GAP,
}
