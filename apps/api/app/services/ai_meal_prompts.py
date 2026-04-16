from __future__ import annotations

from dataclasses import dataclass

from app.schemas.ai import AIProviderMealSuggestionOutput, AIMealSuggestionRequest


@dataclass(frozen=True)
class AIMealSuggestionPromptPlan:
    system_prompt: str
    user_payload: dict[str, object]
    output_schema: dict[str, object]


def _mode_copy(request: AIMealSuggestionRequest) -> str:
    if request.pantry_only:
        return (
            "Pantry-only mode is active. Suggest meals that can be made from the pantry context only. "
            "If there is no perfect recipe, still provide a sensible pantry-based meal using what is available."
        )
    if request.allow_extra_ingredients:
        return (
            "Pantry-plus-extras mode is active. Prefer pantry stock first and keep extra ingredients to a small, practical number."
        )
    return "Prefer pantry stock first and avoid introducing extra ingredients unless there is no sensible alternative."


def build_ai_meal_prompt_plan(
    *,
    household_name: str,
    request: AIMealSuggestionRequest,
    context_payload: dict[str, object],
) -> AIMealSuggestionPromptPlan:
    max_time_copy = (
        f"Keep the total prep and cook time at or below {request.max_total_minutes} minutes."
        if request.max_total_minutes is not None
        else "Keep the meal practical for a normal home cook."
    )
    near_expiry_copy = (
        "Prioritise near-expiry pantry items where they fit naturally."
        if request.prioritize_near_expiry
        else "Use near-expiry items when helpful, but do not force them into every suggestion."
    )
    portions_copy = request.people_count + request.extra_portion_count

    return AIMealSuggestionPromptPlan(
        system_prompt=(
            "You are the meal suggestion engine for a household pantry application. "
            "Return valid JSON only. "
            "Use the structured household, dietary, pantry, and recipe-candidate context exactly as provided. "
            "Do not claim to update pantry stock or save recipes. "
            "Suggest 3 meal ideas when possible, otherwise return 2 strong options. "
            f"{_mode_copy(request)} "
            f"{max_time_copy} "
            f"{near_expiry_copy} "
            f"The meal should suit {portions_copy} total portions and the requested {request.meal_type} meal type. "
            "When you reference pantry products, prefer the pantry product external IDs provided in context and keep ingredient units aligned to pantry units where possible. "
            "Keep steps concise and realistic."
        ),
        user_payload={
            "household_name": household_name,
            "request": request.model_dump(mode="json"),
            "contract": {
                "output_type": "AIProviderMealSuggestionOutput",
                "notes": [
                    "Return 2 to 3 suggestions.",
                    "Keep titles specific and readable.",
                    "Every suggestion needs ingredients and step-by-step instructions.",
                    "quantity must be numeric only; keep units in unit and move phrases like 'to taste' into note.",
                    "Mark truly extra ingredients with is_extra_ingredient=true.",
                    "Use source.kind=household_recipe_reference only when a recipe candidate from context clearly fits.",
                ],
            },
            "context": context_payload,
        },
        output_schema=AIProviderMealSuggestionOutput.model_json_schema(),
    )
