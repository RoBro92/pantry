from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from urllib.parse import SplitResult, urlsplit, urlunsplit

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.household import Household
from app.models.recipe import Recipe
from app.models.recipe_ingredient import RecipeIngredient
from app.models.recipe_url_import import RecipeURLImport
from app.models.user import User
from app.schemas.recipes import RecipeIngredientInput
from app.services.audit import record_audit_event
from app.services.network_policy import validate_public_http_url
from app.services.pantry_normalization import normalize_lookup_name, normalize_unit, require_text
from app.services.recipe_matching import resolve_ingredient_product_match


def _validate_quantity(quantity: Decimal) -> Decimal:
    if quantity <= Decimal("0"):
        raise ValueError("Ingredient quantity must be greater than zero.")
    return quantity.quantize(Decimal("0.001"))


def normalize_recipe_source_url(url: str) -> str:
    raw_url = require_text(url, field_name="Recipe URL")
    parsed = urlsplit(raw_url)

    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Recipe URL must use http or https.")
    if not parsed.netloc:
        raise ValueError("Recipe URL must include a host.")
    if parsed.username or parsed.password:
        raise ValueError("Recipe URL must not include embedded credentials.")

    hostname = parsed.hostname.lower() if parsed.hostname else ""
    netloc_host = f"[{hostname}]" if ":" in hostname else hostname
    port = parsed.port
    if port and not (
        (parsed.scheme.lower() == "http" and port == 80)
        or (parsed.scheme.lower() == "https" and port == 443)
    ):
        netloc = f"{netloc_host}:{port}"
    else:
        netloc = netloc_host

    normalized = SplitResult(
        scheme=parsed.scheme.lower(),
        netloc=netloc,
        path=parsed.path or "/",
        query=parsed.query,
        fragment="",
    )
    normalized_url = urlunsplit(normalized)
    return validate_public_http_url(normalized_url, field_name="Recipe URL", resolve_host=False)


def get_recipe_by_external_id(
    db: Session,
    *,
    household: Household,
    external_id: str,
) -> Recipe | None:
    return db.scalar(
        select(Recipe)
        .where(Recipe.household_id == household.id)
        .where(Recipe.external_id == external_id)
        .options(selectinload(Recipe.ingredients).selectinload(RecipeIngredient.product))
    )


def _normalize_recipe_ingredient(
    db: Session,
    *,
    household: Household,
    ingredient: RecipeIngredientInput,
    position: int,
) -> RecipeIngredient:
    display_name = require_text(ingredient.name, field_name="Ingredient name")
    normalized_quantity = _validate_quantity(ingredient.quantity)
    normalized_unit = normalize_unit(ingredient.unit)
    normalized_note = require_text(ingredient.note, field_name="Ingredient note") if ingredient.note else None
    product, match_source = resolve_ingredient_product_match(
        db,
        household=household,
        ingredient_name=display_name,
        product_external_id=ingredient.product_external_id,
    )

    return RecipeIngredient(
        household_id=household.id,
        product_id=product.id if product is not None else None,
        position=position,
        name=display_name,
        normalized_name=normalize_lookup_name(display_name),
        quantity=normalized_quantity,
        unit=normalized_unit,
        note=normalized_note,
        match_source=match_source,
    )


def _replace_recipe_ingredients(
    db: Session,
    *,
    recipe: Recipe,
    household: Household,
    ingredients: Sequence[RecipeIngredientInput],
) -> None:
    if not ingredients:
        raise ValueError("At least one ingredient is required.")

    db.execute(delete(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id))
    recipe.ingredients = []
    db.flush()

    normalized_ingredients = [
        _normalize_recipe_ingredient(
            db,
            household=household,
            ingredient=ingredient,
            position=index,
        )
        for index, ingredient in enumerate(ingredients, start=1)
    ]

    for ingredient in normalized_ingredients:
        ingredient.recipe_id = recipe.id
        db.add(ingredient)

    recipe.ingredients = normalized_ingredients


def create_recipe(
    db: Session,
    *,
    household: Household,
    actor: User,
    title: str,
    notes: str | None,
    ingredients: Sequence[RecipeIngredientInput],
) -> Recipe:
    return create_recipe_record(
        db,
        household=household,
        actor=actor,
        title=title,
        notes=notes,
        ingredients=ingredients,
        source_kind="manual",
        source_url=None,
        audit_action="recipe.created",
    )


def create_recipe_record(
    db: Session,
    *,
    household: Household,
    actor: User | None,
    title: str,
    notes: str | None,
    ingredients: Sequence[RecipeIngredientInput],
    source_kind: str,
    source_url: str | None,
    audit_action: str,
) -> Recipe:
    display_title = require_text(title, field_name="Recipe title")
    recipe = Recipe(
        household_id=household.id,
        title=display_title,
        normalized_title=normalize_lookup_name(display_title),
        notes=require_text(notes, field_name="Recipe notes") if notes else None,
        source_kind=require_text(source_kind, field_name="Recipe source kind"),
        source_url=require_text(source_url, field_name="Recipe source URL") if source_url else None,
    )
    db.add(recipe)
    db.flush()

    _replace_recipe_ingredients(db, recipe=recipe, household=household, ingredients=ingredients)
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action=audit_action,
        target_type="recipe",
        target_external_id=recipe.external_id,
        event_metadata={
            "title": recipe.title,
            "ingredient_count": len(recipe.ingredients),
            "source_kind": recipe.source_kind,
        },
    )
    db.commit()
    return get_recipe_by_external_id(db, household=household, external_id=recipe.external_id) or recipe


def update_recipe(
    db: Session,
    *,
    household: Household,
    actor: User,
    recipe_external_id: str,
    title: str,
    notes: str | None,
    ingredients: Sequence[RecipeIngredientInput],
) -> Recipe:
    recipe = get_recipe_by_external_id(db, household=household, external_id=recipe_external_id)
    if recipe is None:
        raise ValueError("Recipe not found.")

    recipe.title = require_text(title, field_name="Recipe title")
    recipe.normalized_title = normalize_lookup_name(recipe.title)
    recipe.notes = require_text(notes, field_name="Recipe notes") if notes else None

    _replace_recipe_ingredients(db, recipe=recipe, household=household, ingredients=ingredients)
    db.add(recipe)
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="recipe.updated",
        target_type="recipe",
        target_external_id=recipe.external_id,
        event_metadata={
            "title": recipe.title,
            "ingredient_count": len(recipe.ingredients),
        },
    )
    db.commit()
    return get_recipe_by_external_id(db, household=household, external_id=recipe.external_id) or recipe


def create_recipe_url_import(
    db: Session,
    *,
    household: Household,
    actor: User,
    url: str,
) -> RecipeURLImport:
    normalized_url = normalize_recipe_source_url(url)
    record = RecipeURLImport(
        household_id=household.id,
        requested_by_user_id=actor.id,
        source_url=require_text(url, field_name="Recipe URL"),
        normalized_url=normalized_url,
        status="queued",
        note="Queued for background recipe import.",
    )
    db.add(record)
    db.flush()
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="recipe.url_import.requested",
        target_type="recipe_url_import",
        target_external_id=record.external_id,
        event_metadata={
            "source_url": normalized_url,
            "status": record.status,
        },
    )
    db.commit()
    db.refresh(record)
    return record
