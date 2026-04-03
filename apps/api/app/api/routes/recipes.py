from __future__ import annotations

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps.auth import get_current_user
from app.api.deps.tenancy import require_household_access
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.recipes import (
    CreateRecipeRequest,
    CreateRecipeURLImportRequest,
    RecipeDetailResponse,
    RecipeListResponse,
    RecipeURLImportSummary,
    UpdateRecipeRequest,
)
from app.services.platform_features import FLAG_RECIPE_URL_IMPORTS, require_feature_enabled
from app.services.recipe_catalog import create_recipe, create_recipe_url_import, update_recipe
from app.services.recipe_queries import build_recipe_detail_response, build_recipe_list_response
from app.services.tenancy import HouseholdAccess
from app.services.usage_counters import check_usage_quota

router = APIRouter(prefix="/households/{household_external_id}", tags=["recipes"])


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _ensure_recipe_url_imports_enabled(db: Session, *, access: HouseholdAccess) -> None:
    require_feature_enabled(
        db,
        flag_key=FLAG_RECIPE_URL_IMPORTS,
        household=access.household,
        disabled_message="Recipe URL imports are disabled for this household.",
    )


@router.get("/recipes", response_model=RecipeListResponse)
def get_recipes(
    db: Session = Depends(get_db_session),
    access: HouseholdAccess = Depends(require_household_access()),
):
    return build_recipe_list_response(db, access=access)


@router.get("/recipes/{recipe_external_id}", response_model=RecipeDetailResponse)
def get_recipe(
    recipe_external_id: str,
    db: Session = Depends(get_db_session),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        return build_recipe_detail_response(db, access=access, recipe_external_id=recipe_external_id)
    except ValueError as exc:
        if str(exc) == "Recipe not found.":
            raise _not_found(str(exc)) from exc
        raise _bad_request(exc) from exc


@router.post("/recipes", response_model=RecipeDetailResponse, status_code=status.HTTP_201_CREATED)
def post_recipe(
    payload: CreateRecipeRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        recipe = create_recipe(
            db,
            household=access.household,
            actor=current_user,
            title=payload.title,
            notes=payload.notes,
            ingredients=payload.ingredients,
        )
        return build_recipe_detail_response(db, access=access, recipe_external_id=recipe.external_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.put("/recipes/{recipe_external_id}", response_model=RecipeDetailResponse)
def put_recipe(
    recipe_external_id: str,
    payload: UpdateRecipeRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
    ):
    try:
        recipe = update_recipe(
            db,
            household=access.household,
            actor=current_user,
            recipe_external_id=recipe_external_id,
            title=payload.title,
            notes=payload.notes,
            ingredients=payload.ingredients,
        )
        return build_recipe_detail_response(db, access=access, recipe_external_id=recipe.external_id)
    except ValueError as exc:
        if str(exc) == "Recipe not found.":
            raise _not_found(str(exc)) from exc
        raise _bad_request(exc) from exc


@router.post("/recipe-imports/url", response_model=RecipeURLImportSummary, status_code=status.HTTP_201_CREATED)
def post_recipe_url_import(
    payload: CreateRecipeURLImportRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        _ensure_recipe_url_imports_enabled(db, access=access)
        check_usage_quota(
            db,
            counter_key="recipe_url_imports",
            scope_type="household",
            scope_key=access.household.external_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    try:
        record = create_recipe_url_import(
            db,
            household=access.household,
            actor=current_user,
            url=payload.url,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return RecipeURLImportSummary(
        external_id=record.external_id,
        source_url=record.source_url,
        normalized_url=record.normalized_url,
        status=record.status,
        note=record.note,
        recipe_external_id=record.recipe.external_id if record.recipe is not None else None,
        created_at=record.created_at,
    )
