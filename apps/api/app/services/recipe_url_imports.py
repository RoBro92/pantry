from __future__ import annotations

import json
import re
from fractions import Fraction
from html import unescape
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.recipe import Recipe
from app.models.recipe_url_import import RecipeURLImport
from app.schemas.recipes import RecipeIngredientInput
from app.services.audit import record_audit_event
from app.services.recipe_catalog import create_recipe_record

JSON_LD_RE = re.compile(
    r"<script[^>]*type=['\"]application/ld\+json['\"][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
WHITESPACE_RE = re.compile(r"\s+")


def _claim_next_recipe_url_import(db: Session) -> RecipeURLImport | None:
    record = db.scalar(
        select(RecipeURLImport)
        .where(RecipeURLImport.status == "queued")
        .order_by(RecipeURLImport.created_at.asc())
    )
    if record is None:
        return None

    record.status = "processing"
    record.note = "Fetching recipe metadata."
    db.add(record)
    db.commit()
    return db.scalar(select(RecipeURLImport).where(RecipeURLImport.id == record.id))


def _load_record_by_id(db: Session, *, record_id) -> RecipeURLImport | None:
    return db.scalar(select(RecipeURLImport).where(RecipeURLImport.id == record_id))


def _fetch_recipe_html(url: str) -> str:
    with httpx.Client(follow_redirects=True, timeout=10.0) as client:
        response = client.get(url, headers={"user-agent": "PantryRecipeImporter/0.1"})
        response.raise_for_status()
    return response.text


def _iter_json_ld_candidates(payload: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        candidates.append(payload)
        for value in payload.values():
            candidates.extend(_iter_json_ld_candidates(value))
    elif isinstance(payload, list):
        for item in payload:
            candidates.extend(_iter_json_ld_candidates(item))
    return candidates


def _is_recipe_type(value: Any) -> bool:
    if isinstance(value, str):
        return value.casefold() == "recipe"
    if isinstance(value, list):
        return any(_is_recipe_type(item) for item in value)
    return False


def _extract_recipe_json_ld(html: str) -> dict[str, Any] | None:
    for block in JSON_LD_RE.findall(html):
        try:
            payload = json.loads(unescape(block.strip()))
        except json.JSONDecodeError:
            continue
        for candidate in _iter_json_ld_candidates(payload):
            if _is_recipe_type(candidate.get("@type")):
                return candidate
    return None


def _extract_html_title(html: str) -> str | None:
    match = TITLE_RE.search(html)
    if not match:
        return None
    return WHITESPACE_RE.sub(" ", unescape(match.group(1))).strip() or None


def _parse_fractional_number(value: str) -> Fraction | None:
    text = value.strip()
    if not text:
        return None
    parts = text.split()
    try:
        if len(parts) == 2 and "/" in parts[1]:
            return Fraction(parts[0]) + Fraction(parts[1])
        if "/" in text and " " not in text:
            return Fraction(text)
        return Fraction(text)
    except ValueError:
        return None
    except ZeroDivisionError:
        return None


def _ingredient_from_text(line: str) -> RecipeIngredientInput:
    normalized = WHITESPACE_RE.sub(" ", line).strip()
    if not normalized:
        raise ValueError("Recipe ingredient text is required.")

    match = re.match(
        r"^(?P<quantity>\d+(?:\.\d+)?(?:\s+\d+/\d+|\s*/\s*\d+)?)\s+(?P<unit>[A-Za-z][\w.-]*)\s+(?P<name>.+)$",
        normalized,
    )
    if match:
        quantity_fraction = _parse_fractional_number(match.group("quantity"))
        if quantity_fraction is not None:
            return RecipeIngredientInput(
                name=match.group("name").strip(),
                quantity=str(round(float(quantity_fraction), 3)),
                unit=match.group("unit").strip(),
            )

    match = re.match(r"^(?P<quantity>\d+(?:\.\d+)?)\s+(?P<name>.+)$", normalized)
    if match:
        return RecipeIngredientInput(
            name=match.group("name").strip(),
            quantity=match.group("quantity"),
            unit="count",
        )

    return RecipeIngredientInput(name=normalized, quantity="1.000", unit="count")


def _build_recipe_payload(html: str, *, fallback_title: str) -> tuple[str, list[RecipeIngredientInput]]:
    recipe_json_ld = _extract_recipe_json_ld(html)
    if recipe_json_ld is None:
        raise ValueError("No structured recipe metadata was found at the provided URL.")

    ingredient_values = [
        item.strip()
        for item in recipe_json_ld.get("recipeIngredient", [])
        if isinstance(item, str) and item.strip()
    ]
    if not ingredient_values:
        raise ValueError("Structured recipe metadata did not include any ingredients.")

    title = str(recipe_json_ld.get("name") or "").strip() or fallback_title
    if not title:
        raise ValueError("Structured recipe metadata did not include a usable title.")

    return title, [_ingredient_from_text(item) for item in ingredient_values]


def process_next_recipe_url_import() -> bool:
    with SessionLocal() as db:
        record = _claim_next_recipe_url_import(db)
        if record is None:
            return False

        try:
            html = _fetch_recipe_html(record.normalized_url)
            fallback_title = _extract_html_title(html) or record.normalized_url
            title, ingredients = _build_recipe_payload(html, fallback_title=fallback_title)

            recipe = create_recipe_record(
                db,
                household=record.household,
                actor=None,
                title=title,
                notes=None,
                ingredients=ingredients,
                source_kind="url_import",
                source_url=record.normalized_url,
                audit_action="recipe.imported_from_url",
            )

            refreshed = _load_record_by_id(db, record_id=record.id)
            if refreshed is None:
                raise ValueError("Recipe URL import disappeared during processing.")

            refreshed.recipe_id = recipe.id
            refreshed.status = "imported"
            refreshed.note = "Recipe imported from structured metadata."
            db.add(refreshed)
            record_audit_event(
                db,
                household=refreshed.household,
                actor=None,
                action="recipe.url_import.completed",
                target_type="recipe_url_import",
                target_external_id=refreshed.external_id,
                event_metadata={
                    "recipe_external_id": recipe.external_id,
                    "source_url": refreshed.normalized_url,
                },
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            refreshed = _load_record_by_id(db, record_id=record.id)
            if refreshed is None:
                raise
            refreshed.status = "failed"
            refreshed.note = str(exc)
            db.add(refreshed)
            record_audit_event(
                db,
                household=refreshed.household,
                actor=None,
                action="recipe.url_import.failed",
                target_type="recipe_url_import",
                target_external_id=refreshed.external_id,
                event_metadata={
                    "source_url": refreshed.normalized_url,
                    "error": str(exc),
                },
            )
            db.commit()

    return True
