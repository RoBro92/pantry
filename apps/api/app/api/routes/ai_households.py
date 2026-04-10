from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.api.deps.tenancy import require_household_access
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.ai import (
    AIFeatureStatusSummary,
    AIMealPlannerResponse,
    AIMealSuggestionRequest,
    AIMealSuggestionResponse,
    AISuggestionRequest,
    AISuggestionResponse,
    CompleteAIMealSuggestionRequest,
    CompleteAIMealSuggestionResponse,
)
from app.services.ai_meal_suggestions import (
    complete_ai_meal_suggestion,
    generate_ai_meal_suggestions,
    get_ai_meal_planner,
)
from app.services.ai_suggestions import build_household_ai_feature_status, generate_household_ai_suggestions
from app.services.tenancy import HouseholdAccess

router = APIRouter(prefix="/households/{household_external_id}", tags=["household-ai"])


@router.get("/ai/status", response_model=AIFeatureStatusSummary)
def get_ai_status(
    db: Session = Depends(get_db_session),
    access: HouseholdAccess = Depends(require_household_access()),
):
    return build_household_ai_feature_status(db, household=access.household)


def _http_error_from_value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if "disabled for this household" in message.lower():
        status_code = status.HTTP_403_FORBIDDEN
    elif "provider" in message.lower() or "no ai provider" in message.lower() or "disabled" in message.lower():
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=status_code, detail=message)


@router.get("/ai/meal-planner", response_model=AIMealPlannerResponse)
def get_meal_planner(
    db: Session = Depends(get_db_session),
    access: HouseholdAccess = Depends(require_household_access()),
):
    return get_ai_meal_planner(db, access=access)


@router.post("/ai/suggestions", response_model=AISuggestionResponse)
def post_ai_suggestions(
    payload: AISuggestionRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        return generate_household_ai_suggestions(
            db,
            access=access,
            actor=current_user,
            request=payload,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc) from exc


@router.post("/ai/meal-suggestions", response_model=AIMealSuggestionResponse)
def post_ai_meal_suggestions(
    payload: AIMealSuggestionRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        return generate_ai_meal_suggestions(
            db,
            access=access,
            actor=current_user,
            request=payload,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc) from exc


@router.post("/ai/meal-suggestions/complete", response_model=CompleteAIMealSuggestionResponse)
def post_complete_ai_meal_suggestion(
    payload: CompleteAIMealSuggestionRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        return complete_ai_meal_suggestion(
            db,
            access=access,
            actor=current_user,
            request=payload,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc) from exc
