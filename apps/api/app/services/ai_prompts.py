from __future__ import annotations

from dataclasses import dataclass

from app.domain.ai import (
    AI_SUGGESTION_BUY_EXTRA,
    AI_SUGGESTION_EXPIRY_FIRST,
    AI_SUGGESTION_MEAL,
    AI_SUGGESTION_RECIPE_GAP,
)
from app.schemas.ai import AIProviderSuggestionOutput, AISuggestionRequest


@dataclass(frozen=True)
class AISuggestionPromptPlan:
    system_prompt: str
    user_payload: dict[str, object]
    output_schema: dict[str, object]


def _goal_copy(kind: str) -> str:
    if kind == AI_SUGGESTION_MEAL:
        return "Generate pantry-aware meal ideas that prefer products already on hand."
    if kind == AI_SUGGESTION_EXPIRY_FIRST:
        return "Generate suggestions that prioritize products expiring soon."
    if kind == AI_SUGGESTION_BUY_EXTRA:
        return "Generate ideas that use current pantry stock and add only a few extra ingredients."
    if kind == AI_SUGGESTION_RECIPE_GAP:
        return "Explain the recipe gap and propose safe substitution ideas based on pantry stock."
    raise ValueError("Unsupported AI suggestion kind.")


def build_suggestion_prompt_plan(
    *,
    household_name: str,
    request: AISuggestionRequest,
    context_payload: dict[str, object],
) -> AISuggestionPromptPlan:
    if request.kind == AI_SUGGESTION_RECIPE_GAP and not request.recipe_external_id:
        raise ValueError("recipe_external_id is required for recipe_gap suggestions.")

    return AISuggestionPromptPlan(
        system_prompt=(
            "You are an assistant for a household pantry application. "
            f"{_goal_copy(request.kind)} "
            "Return valid JSON only. Keep every suggestion advisory and read-only. "
            "Do not claim to modify inventory, recipes, or imports. "
            "Prefer classified pantry products over fallback name-based product data whenever both are available. "
            "Use dietary tags, ingredient families, recipe roles, and substitution groups directly when they are present. "
            "Use the structured pantry and recipe context exactly as provided."
        ),
        user_payload={
            "request": request.model_dump(mode="json"),
            "contract": {
                "output_type": "AIProviderSuggestionOutput",
                "notes": [
                    "Populate suggestions with concise, structured advisory items.",
                    "Prefer pantry products already present in the context.",
                    "Use pantry.classified_products before pantry.fallback_products when choosing pantry matches.",
                    "Use household dietary preferences and classified dietary tags efficiently instead of inferring from names.",
                    "Only include substitution ideas when they fit naturally.",
                ],
            },
            "context": context_payload,
            "household_name": household_name,
        },
        output_schema=AIProviderSuggestionOutput.model_json_schema(),
    )
