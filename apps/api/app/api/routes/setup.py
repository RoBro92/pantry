from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.schemas.auth import SessionResponse
from app.schemas.setup import (
    SetupAIConfigUpdateRequest,
    SetupDietaryUpdateRequest,
    SetupHouseholdUpdateRequest,
    SetupPublicURLUpdateRequest,
    SetupSMTPConfigUpdateRequest,
    SetupStatusResponse,
    SetupUsersUpdateRequest,
    SetupWelcomeUpdateRequest,
    SetupWizardStateResponse,
)
from app.services.auth import build_session_response
from app.services.setup import (
    finalize_setup,
    get_setup_status,
    get_setup_wizard_state,
    update_setup_ai,
    update_setup_dietary,
    update_setup_household,
    update_setup_public_url,
    update_setup_smtp,
    update_setup_users,
    update_setup_welcome,
)

router = APIRouter(prefix="/setup", tags=["setup"])


def _handle_setup_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/status", response_model=SetupStatusResponse)
def get_status(db: Session = Depends(get_db_session)):
    return get_setup_status(db)


@router.get("/wizard", response_model=SetupWizardStateResponse)
def get_wizard_state(db: Session = Depends(get_db_session)):
    return get_setup_wizard_state(db)


@router.put("/wizard/welcome", response_model=SetupWizardStateResponse)
def put_welcome(payload: SetupWelcomeUpdateRequest, db: Session = Depends(get_db_session)):
    return update_setup_welcome(db, payload)


@router.put("/wizard/users", response_model=SetupWizardStateResponse)
def put_users(payload: SetupUsersUpdateRequest, db: Session = Depends(get_db_session)):
    try:
        return update_setup_users(db, payload)
    except ValueError as exc:
        raise _handle_setup_error(exc) from exc


@router.put("/wizard/household", response_model=SetupWizardStateResponse)
def put_household(payload: SetupHouseholdUpdateRequest, db: Session = Depends(get_db_session)):
    return update_setup_household(db, payload)


@router.put("/wizard/public-url", response_model=SetupWizardStateResponse)
def put_public_url(payload: SetupPublicURLUpdateRequest, db: Session = Depends(get_db_session)):
    try:
        return update_setup_public_url(db, payload)
    except ValueError as exc:
        raise _handle_setup_error(exc) from exc


@router.put("/wizard/dietary", response_model=SetupWizardStateResponse)
def put_dietary(payload: SetupDietaryUpdateRequest, db: Session = Depends(get_db_session)):
    return update_setup_dietary(db, payload)


@router.put("/wizard/ai", response_model=SetupWizardStateResponse)
def put_ai(payload: SetupAIConfigUpdateRequest, db: Session = Depends(get_db_session)):
    try:
        return update_setup_ai(db, payload)
    except ValueError as exc:
        raise _handle_setup_error(exc) from exc


@router.put("/wizard/smtp", response_model=SetupWizardStateResponse)
def put_smtp(payload: SetupSMTPConfigUpdateRequest, db: Session = Depends(get_db_session)):
    try:
        return update_setup_smtp(db, payload)
    except ValueError as exc:
        raise _handle_setup_error(exc) from exc


@router.post("/wizard/finalize", response_model=SessionResponse)
def post_finalize_setup(request: Request, db: Session = Depends(get_db_session)):
    try:
        user = finalize_setup(db)
    except ValueError as exc:
        raise _handle_setup_error(exc) from exc

    request.session.clear()
    request.session["user_external_id"] = user.external_id
    return build_session_response(user)
