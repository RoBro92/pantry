from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.product import Product
from app.models.recipe import Recipe
from app.models.recipe_ingredient import RecipeIngredient
from app.models.stock_lot import StockLot
from app.schemas.recipes import (
    IngredientCoverageSummary,
    LinkedProductSummary,
    RecipeCoverageSummary,
    RecipeDetail,
    RecipeDetailResponse,
    RecipeIngredientSummary,
    RecipeListItem,
    RecipeListResponse,
    ShoppingGapItemSummary,
)
from app.services.recipe_catalog import get_recipe_by_external_id
from app.services.tenancy import HouseholdAccess


@dataclass(frozen=True)
class IngredientCoverageResult:
    ingredient: RecipeIngredient
    status: str
    pantry_available_quantity: Decimal
    covered_quantity: Decimal
    missing_quantity: Decimal
    comparison_unit: str | None
    reason: str | None


def _load_recipes(db: Session, *, household_id) -> list[Recipe]:
    return db.scalars(
        select(Recipe)
        .where(Recipe.household_id == household_id)
        .options(selectinload(Recipe.ingredients).selectinload(RecipeIngredient.product))
        .order_by(Recipe.updated_at.desc(), Recipe.title.asc())
    ).all()


def _load_pantry_totals(db: Session, *, household_id) -> dict[str, tuple[Decimal, str]]:
    rows = db.execute(
        select(
            StockLot.product_id,
            StockLot.unit,
            func.sum(StockLot.quantity),
        )
        .where(StockLot.household_id == household_id)
        .where(StockLot.depleted_at.is_(None))
        .where(StockLot.quantity > Decimal("0"))
        .group_by(StockLot.product_id, StockLot.unit)
    ).all()
    return {str(product_id): (total_quantity, unit) for product_id, unit, total_quantity in rows}


def _compute_ingredient_coverage(
    recipe: Recipe,
    *,
    pantry_totals: dict[str, tuple[Decimal, str]],
) -> list[IngredientCoverageResult]:
    remaining_totals = {product_id: total for product_id, total in pantry_totals.items()}
    coverage_results: list[IngredientCoverageResult] = []

    for ingredient in sorted(recipe.ingredients, key=lambda item: item.position):
        if ingredient.product is None:
            coverage_results.append(
                IngredientCoverageResult(
                    ingredient=ingredient,
                    status="missing",
                    pantry_available_quantity=Decimal("0.000"),
                    covered_quantity=Decimal("0.000"),
                    missing_quantity=ingredient.quantity,
                    comparison_unit=None,
                    reason="No pantry product link is available for this ingredient.",
                )
            )
            continue

        product_key = str(ingredient.product_id)
        pantry_total, pantry_unit = remaining_totals.get(product_key, (Decimal("0.000"), ingredient.product.default_unit))
        if pantry_unit != ingredient.unit:
            coverage_results.append(
                IngredientCoverageResult(
                    ingredient=ingredient,
                    status="missing",
                    pantry_available_quantity=Decimal("0.000"),
                    covered_quantity=Decimal("0.000"),
                    missing_quantity=ingredient.quantity,
                    comparison_unit=pantry_unit,
                    reason="Inventory stock uses a different unit than this ingredient.",
                )
            )
            continue

        covered_quantity = min(pantry_total, ingredient.quantity)
        missing_quantity = (ingredient.quantity - covered_quantity).quantize(Decimal("0.001"))
        remaining_totals[product_key] = (pantry_total - covered_quantity).quantize(Decimal("0.001")), pantry_unit

        if missing_quantity == Decimal("0.000"):
            status = "fully_covered"
        elif covered_quantity > Decimal("0.000"):
            status = "partially_covered"
        else:
            status = "missing"

        coverage_results.append(
            IngredientCoverageResult(
                ingredient=ingredient,
                status=status,
                pantry_available_quantity=pantry_total,
                covered_quantity=covered_quantity,
                missing_quantity=missing_quantity,
                comparison_unit=pantry_unit,
                reason=None,
            )
        )

    return coverage_results


def _build_shopping_gap_items(
    coverage_results: list[IngredientCoverageResult],
) -> list[ShoppingGapItemSummary]:
    buckets: OrderedDict[tuple[str | None, str, str], ShoppingGapItemSummary] = OrderedDict()

    for result in coverage_results:
        if result.missing_quantity <= Decimal("0.000"):
            continue

        product = result.ingredient.product
        is_comparable_product_gap = product is not None and result.comparison_unit == result.ingredient.unit and result.reason is None
        label = product.name if is_comparable_product_gap and product is not None else result.ingredient.name
        key = (
            product.external_id if is_comparable_product_gap and product is not None else None,
            label.casefold(),
            result.ingredient.unit,
        )

        existing = buckets.get(key)
        if existing is None:
            buckets[key] = ShoppingGapItemSummary(
                label=label,
                quantity=result.missing_quantity,
                unit=result.ingredient.unit,
                product_external_id=product.external_id if is_comparable_product_gap and product is not None else None,
                product_name=product.name if is_comparable_product_gap and product is not None else None,
                ingredient_count=1,
            )
            continue

        existing.quantity = (existing.quantity + result.missing_quantity).quantize(Decimal("0.001"))
        existing.ingredient_count += 1

    return list(buckets.values())


def _build_recipe_coverage_summary(
    coverage_results: list[IngredientCoverageResult],
    *,
    shopping_gap_count: int,
) -> RecipeCoverageSummary:
    fully_covered_count = sum(1 for result in coverage_results if result.status == "fully_covered")
    partially_covered_count = sum(1 for result in coverage_results if result.status == "partially_covered")
    missing_count = sum(1 for result in coverage_results if result.status == "missing")

    if missing_count == 0 and partially_covered_count == 0:
        status = "fully_covered"
    elif missing_count == len(coverage_results):
        status = "missing"
    else:
        status = "partially_covered"

    return RecipeCoverageSummary(
        status=status,
        fully_covered_count=fully_covered_count,
        partially_covered_count=partially_covered_count,
        missing_count=missing_count,
        shopping_gap_count=shopping_gap_count,
    )


def _build_recipe_detail(recipe: Recipe, *, pantry_totals: dict[str, tuple[Decimal, str]]) -> RecipeDetail:
    coverage_results = _compute_ingredient_coverage(recipe, pantry_totals=pantry_totals)
    shopping_gap_items = _build_shopping_gap_items(coverage_results)
    coverage_summary = _build_recipe_coverage_summary(
        coverage_results,
        shopping_gap_count=len(shopping_gap_items),
    )

    return RecipeDetail(
        external_id=recipe.external_id,
        title=recipe.title,
        notes=recipe.notes,
        source_kind=recipe.source_kind,
        source_url=recipe.source_url,
        ingredient_count=len(recipe.ingredients),
        pantry_coverage=coverage_summary,
        ingredients=[
            RecipeIngredientSummary(
                external_id=result.ingredient.external_id,
                position=result.ingredient.position,
                name=result.ingredient.name,
                quantity=result.ingredient.quantity,
                unit=result.ingredient.unit,
                note=result.ingredient.note,
                match_source=result.ingredient.match_source,
                product=(
                    LinkedProductSummary(
                        external_id=result.ingredient.product.external_id,
                        name=result.ingredient.product.name,
                        default_unit=result.ingredient.product.default_unit,
                    )
                    if result.ingredient.product is not None
                    else None
                ),
                coverage=IngredientCoverageSummary(
                    status=result.status,
                    pantry_available_quantity=result.pantry_available_quantity,
                    covered_quantity=result.covered_quantity,
                    missing_quantity=result.missing_quantity,
                    comparison_unit=result.comparison_unit,
                    reason=result.reason,
                ),
            )
            for result in coverage_results
        ],
        shopping_gap_items=shopping_gap_items,
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
    )


def build_recipe_list_response(
    db: Session,
    *,
    access: HouseholdAccess,
) -> RecipeListResponse:
    recipes = _load_recipes(db, household_id=access.household.id)
    pantry_totals = _load_pantry_totals(db, household_id=access.household.id)

    return RecipeListResponse(
        household_external_id=access.household.external_id,
        household_name=access.household.name,
        effective_role=access.effective_role,
        can_administer=access.can_administer,
        recipes=[
            RecipeListItem(
                external_id=recipe.external_id,
                title=recipe.title,
                notes=recipe.notes,
                source_kind=recipe.source_kind,
                source_url=recipe.source_url,
                ingredient_count=len(recipe.ingredients),
                pantry_coverage=_build_recipe_detail(recipe, pantry_totals=pantry_totals).pantry_coverage,
                updated_at=recipe.updated_at,
            )
            for recipe in recipes
        ],
    )


def build_recipe_detail_response(
    db: Session,
    *,
    access: HouseholdAccess,
    recipe_external_id: str,
) -> RecipeDetailResponse:
    recipe = get_recipe_by_external_id(db, household=access.household, external_id=recipe_external_id)
    if recipe is None:
        raise ValueError("Recipe not found.")

    pantry_totals = _load_pantry_totals(db, household_id=access.household.id)

    return RecipeDetailResponse(
        household_external_id=access.household.external_id,
        household_name=access.household.name,
        effective_role=access.effective_role,
        can_administer=access.can_administer,
        recipe=_build_recipe_detail(recipe, pantry_totals=pantry_totals),
    )
