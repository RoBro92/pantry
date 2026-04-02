from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RecipeIngredientInput(BaseModel):
    name: str
    quantity: Decimal
    unit: str
    note: str | None = None
    product_external_id: str | None = None


class CreateRecipeRequest(BaseModel):
    title: str
    notes: str | None = None
    ingredients: list[RecipeIngredientInput] = Field(default_factory=list)


class UpdateRecipeRequest(BaseModel):
    title: str
    notes: str | None = None
    ingredients: list[RecipeIngredientInput] = Field(default_factory=list)


class CreateRecipeURLImportRequest(BaseModel):
    url: str


class LinkedProductSummary(BaseModel):
    external_id: str
    name: str
    default_unit: str


class IngredientCoverageSummary(BaseModel):
    status: str
    pantry_available_quantity: Decimal
    covered_quantity: Decimal
    missing_quantity: Decimal
    comparison_unit: str | None = None
    reason: str | None = None


class RecipeIngredientSummary(BaseModel):
    external_id: str
    position: int
    name: str
    quantity: Decimal
    unit: str
    note: str | None
    match_source: str
    product: LinkedProductSummary | None = None
    coverage: IngredientCoverageSummary

    model_config = ConfigDict(from_attributes=True)


class ShoppingGapItemSummary(BaseModel):
    label: str
    quantity: Decimal
    unit: str
    product_external_id: str | None = None
    product_name: str | None = None
    ingredient_count: int


class RecipeCoverageSummary(BaseModel):
    status: str
    fully_covered_count: int
    partially_covered_count: int
    missing_count: int
    shopping_gap_count: int


class RecipeListItem(BaseModel):
    external_id: str
    title: str
    notes: str | None
    source_kind: str
    source_url: str | None
    ingredient_count: int
    pantry_coverage: RecipeCoverageSummary
    updated_at: datetime


class RecipeDetail(BaseModel):
    external_id: str
    title: str
    notes: str | None
    source_kind: str
    source_url: str | None
    ingredient_count: int
    pantry_coverage: RecipeCoverageSummary
    ingredients: list[RecipeIngredientSummary]
    shopping_gap_items: list[ShoppingGapItemSummary]
    created_at: datetime
    updated_at: datetime


class RecipeListResponse(BaseModel):
    household_external_id: str
    household_name: str
    effective_role: str
    can_administer: bool
    recipes: list[RecipeListItem]


class RecipeDetailResponse(BaseModel):
    household_external_id: str
    household_name: str
    effective_role: str
    can_administer: bool
    recipe: RecipeDetail


class RecipeURLImportSummary(BaseModel):
    external_id: str
    source_url: str
    normalized_url: str
    status: str
    note: str | None
    recipe_external_id: str | None = None
    created_at: datetime

