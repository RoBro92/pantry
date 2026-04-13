from __future__ import annotations


class AIProviderError(RuntimeError):
    def __init__(
        self,
        user_message: str,
        *,
        diagnostic_message: str | None = None,
        category: str = "provider_error",
    ) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.diagnostic_message = diagnostic_message or user_message
        self.category = category


class OpenAISchemaCompatibilityError(ValueError):
    pass
