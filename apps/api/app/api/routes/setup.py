from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db_session
from app.schemas.auth import SessionResponse
from app.schemas.setup import (
    SetupAIConfigUpdateRequest,
    SetupDietaryUpdateRequest,
    SetupHouseholdUpdateRequest,
    SetupModeUpdateRequest,
    SetupPublicURLUpdateRequest,
    SetupSMTPConfigUpdateRequest,
    SetupSMTPTestRequest,
    SetupSMTPTestResponse,
    SetupStatusResponse,
    SetupUsersUpdateRequest,
    SetupWelcomeUpdateRequest,
    SetupWizardStateResponse,
)
from app.services.client_scope import client_scope_from_request
from app.services.rate_limits import hit_rate_limit
from app.services.auth import build_session_response
from app.services.setup import (
    finalize_setup,
    get_setup_status,
    get_setup_wizard_state,
    is_setup_complete,
    stage_setup_restore_upload,
    update_setup_ai,
    update_setup_dietary,
    update_setup_household,
    update_setup_mode,
    update_setup_public_url,
    update_setup_smtp,
    test_setup_smtp,
    update_setup_users,
    update_setup_welcome,
)

router = APIRouter(prefix="/setup", tags=["setup"])


def _handle_setup_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _ensure_setup_is_open(db: Session) -> None:
    if is_setup_complete(db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Initial setup has already been completed.",
        )


def _client_scope(request: Request) -> str:
    return client_scope_from_request(request)


def _limit_setup_mutation(request: Request) -> None:
    settings = get_settings()
    limit = hit_rate_limit(
        "setup:mutation",
        _client_scope(request),
        limit=settings.setup_mutation_rate_limit_attempts,
        window_seconds=settings.setup_mutation_rate_limit_window_seconds,
    )
    if not limit.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many setup attempts. Please wait before trying again.",
        )


@router.get("/status", response_model=SetupStatusResponse)
def get_status(db: Session = Depends(get_db_session)):
    return get_setup_status(db)


@router.get("/wizard", response_model=SetupWizardStateResponse)
def get_wizard_state(db: Session = Depends(get_db_session)):
    _ensure_setup_is_open(db)
    return get_setup_wizard_state(db)


@router.put("/wizard/welcome", response_model=SetupWizardStateResponse)
def put_welcome(payload: SetupWelcomeUpdateRequest, request: Request, db: Session = Depends(get_db_session)):
    _ensure_setup_is_open(db)
    _limit_setup_mutation(request)
    return update_setup_welcome(db, payload)


@router.put("/wizard/mode", response_model=SetupWizardStateResponse)
def put_mode(payload: SetupModeUpdateRequest, request: Request, db: Session = Depends(get_db_session)):
    _ensure_setup_is_open(db)
    _limit_setup_mutation(request)
    return update_setup_mode(db, payload)


@router.post("/wizard/restore-upload", response_model=SetupWizardStateResponse)
async def post_restore_upload(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
):
    _ensure_setup_is_open(db)
    _limit_setup_mutation(request)
    try:
        return await stage_setup_restore_upload(db, file)
    except ValueError as exc:
        raise _handle_setup_error(exc) from exc


@router.put("/wizard/users", response_model=SetupWizardStateResponse)
def put_users(payload: SetupUsersUpdateRequest, request: Request, db: Session = Depends(get_db_session)):
    _ensure_setup_is_open(db)
    _limit_setup_mutation(request)
    try:
        return update_setup_users(db, payload)
    except ValueError as exc:
        raise _handle_setup_error(exc) from exc


@router.put("/wizard/household", response_model=SetupWizardStateResponse)
def put_household(payload: SetupHouseholdUpdateRequest, request: Request, db: Session = Depends(get_db_session)):
    _ensure_setup_is_open(db)
    _limit_setup_mutation(request)
    return update_setup_household(db, payload)


@router.put("/wizard/public-url", response_model=SetupWizardStateResponse)
def put_public_url(payload: SetupPublicURLUpdateRequest, request: Request, db: Session = Depends(get_db_session)):
    _ensure_setup_is_open(db)
    _limit_setup_mutation(request)
    try:
        return update_setup_public_url(db, payload)
    except ValueError as exc:
        raise _handle_setup_error(exc) from exc


@router.put("/wizard/dietary", response_model=SetupWizardStateResponse)
def put_dietary(payload: SetupDietaryUpdateRequest, request: Request, db: Session = Depends(get_db_session)):
    _ensure_setup_is_open(db)
    _limit_setup_mutation(request)
    return update_setup_dietary(db, payload)


@router.put("/wizard/ai", response_model=SetupWizardStateResponse)
def put_ai(payload: SetupAIConfigUpdateRequest, request: Request, db: Session = Depends(get_db_session)):
    _ensure_setup_is_open(db)
    _limit_setup_mutation(request)
    try:
        return update_setup_ai(db, payload)
    except ValueError as exc:
        raise _handle_setup_error(exc) from exc


@router.put("/wizard/smtp", response_model=SetupWizardStateResponse)
def put_smtp(payload: SetupSMTPConfigUpdateRequest, request: Request, db: Session = Depends(get_db_session)):
    _ensure_setup_is_open(db)
    _limit_setup_mutation(request)
    try:
        return update_setup_smtp(db, payload)
    except ValueError as exc:
        raise _handle_setup_error(exc) from exc


@router.post("/wizard/smtp/test", response_model=SetupSMTPTestResponse)
def post_smtp_test(payload: SetupSMTPTestRequest, request: Request, db: Session = Depends(get_db_session)):
    _ensure_setup_is_open(db)
    _limit_setup_mutation(request)
    try:
        return test_setup_smtp(db, payload)
    except ValueError as exc:
        raise _handle_setup_error(exc) from exc


@router.post("/wizard/finalize", response_model=SessionResponse)
def post_finalize_setup(request: Request, db: Session = Depends(get_db_session)):
    _ensure_setup_is_open(db)
    _limit_setup_mutation(request)
    try:
        user = finalize_setup(db)
    except ValueError as exc:
        raise _handle_setup_error(exc) from exc

    request.session.clear()
    request.session["user_external_id"] = user.external_id
    request.session["session_version"] = user.session_version
    return build_session_response(user)
