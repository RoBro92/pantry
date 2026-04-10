from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.schemas.recipes import RecipeDetail
from app.services.recipe_queries import build_recipe_detail_response, build_recipe_list_response
from app.services.tenancy import HouseholdAccess


@dataclass(frozen=True)
class RecipeSuggestionCandidate:
    provider_name: str
    source_kind: str
    recipe_external_id: str
    title: str
    notes: str | None
    source_url: str | None
    pantry_coverage_status: str
    shopping_gap_count: int
    ingredient_count: int
    detail: RecipeDetail


class RecipeSuggestionProvider(Protocol):
    provider_name: str

    def list_candidates(
        self,
        db: Session,
        *,
        access: HouseholdAccess,
        limit: int,
    ) -> list[RecipeSuggestionCandidate]:
        ...


def _coverage_rank(status: str) -> int:
    if status == "fully_covered":
        return 0
    if status == "partially_covered":
        return 1
    return 2


class HouseholdRecipeSuggestionProvider:
    provider_name = "household_recipes"

    def list_candidates(
        self,
        db: Session,
        *,
        access: HouseholdAccess,
        limit: int,
    ) -> list[RecipeSuggestionCandidate]:
        recipe_list = build_recipe_list_response(db, access=access)
        ranked_items = sorted(
            recipe_list.recipes,
            key=lambda item: (
                _coverage_rank(item.pantry_coverage.status),
                item.pantry_coverage.shopping_gap_count,
                -item.updated_at.timestamp(),
                item.title.casefold(),
            ),
        )[:limit]

        candidates: list[RecipeSuggestionCandidate] = []
        for item in ranked_items:
            detail = build_recipe_detail_response(
                db,
                access=access,
                recipe_external_id=item.external_id,
            ).recipe
            candidates.append(
                RecipeSuggestionCandidate(
                    provider_name=self.provider_name,
                    source_kind=item.source_kind,
                    recipe_external_id=item.external_id,
                    title=item.title,
                    notes=item.notes,
                    source_url=item.source_url,
                    pantry_coverage_status=item.pantry_coverage.status,
                    shopping_gap_count=item.pantry_coverage.shopping_gap_count,
                    ingredient_count=item.ingredient_count,
                    detail=detail,
                )
            )
        return candidates


def list_recipe_suggestion_candidates(
    db: Session,
    *,
    access: HouseholdAccess,
    limit: int = 8,
) -> list[RecipeSuggestionCandidate]:
    providers: list[RecipeSuggestionProvider] = [
        HouseholdRecipeSuggestionProvider(),
    ]
    candidates: list[RecipeSuggestionCandidate] = []
    for provider in providers:
        candidates.extend(provider.list_candidates(db, access=access, limit=limit))
    return candidates[:limit]
