from __future__ import annotations

from json import JSONDecodeError

from pydantic import ValidationError

from app.services.ai_providers.errors import AIProviderError


class AIUserFacingError(ValueError):
    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


def summarize_ai_failure(exc: Exception, *, fallback_message: str) -> tuple[str, str, str]:
    if isinstance(exc, AIProviderError):
        return exc.user_message, exc.diagnostic_message, exc.category
    if isinstance(exc, ValidationError):
        return (
            "The AI provider returned a structured response Pantry could not validate.",
            exc.json(),
            "invalid_response",
        )
    if isinstance(exc, JSONDecodeError):
        return (
            "The AI provider returned a structured response Pantry could not parse.",
            str(exc),
            "invalid_response",
        )
    return fallback_message, str(exc), "unknown_error"
