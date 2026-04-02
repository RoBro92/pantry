from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.api.deps.tenancy import require_household_access
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.ai import AIFeatureStatusSummary, AISuggestionRequest, AISuggestionResponse
from app.services.ai_suggestions import build_household_ai_feature_status, generate_household_ai_suggestions
from app.services.tenancy import HouseholdAccess

router = APIRouter(prefix="/households/{household_external_id}", tags=["household-ai"])


@router.get("/ai/status", response_model=AIFeatureStatusSummary)
def get_ai_status(
    db: Session = Depends(get_db_session),
    access: HouseholdAccess = Depends(require_household_access()),
):
    return build_household_ai_feature_status(db, household=access.household)


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
        message = str(exc)
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if "provider" in message.lower() or "no ai provider" in message.lower() or "disabled" in message.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=message) from exc
