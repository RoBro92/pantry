from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    PasswordActionResponse,
    PasswordChangeRequest,
    PasswordResetAvailabilityResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetTokenStatusResponse,
    ProfileUpdateRequest,
    SessionResponse,
)
from app.services.auth import authenticate_user, build_session_response, update_user_profile
from app.services.instance_settings import resolve_password_reset_email_settings
from app.services.password_resets import (
    change_password,
    confirm_password_reset,
    get_password_reset_token_status,
    request_password_reset,
)
from app.services.setup import is_setup_complete

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db_session)):
    if not is_setup_complete(db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pantro setup is not complete yet. Finish the setup wizard first.",
        )

    identifier = payload.identifier or payload.email or ""
    user = authenticate_user(db, identifier, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

    request.session.clear()
    request.session["user_external_id"] = user.external_id
    return build_session_response(user)


@router.post("/logout", response_model=LogoutResponse)
def logout(request: Request, _: User = Depends(get_current_user)):
    request.session.clear()
    return LogoutResponse(ok=True)


@router.get("/session", response_model=SessionResponse)
def current_session(
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    if not is_setup_complete(db):
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pantro setup is not complete yet. Finish the setup wizard first.",
        )
    response.headers["cache-control"] = "no-store"
    request.session["user_external_id"] = current_user.external_id
    return build_session_response(current_user)


@router.get("/password-reset/status", response_model=PasswordResetAvailabilityResponse)
def get_password_reset_status(db: Session = Depends(get_db_session)):
    if not is_setup_complete(db):
        return PasswordResetAvailabilityResponse(
            is_available=False,
            reason="Password reset is unavailable until setup is complete.",
        )
    settings = resolve_password_reset_email_settings(db)
    return PasswordResetAvailabilityResponse(
        is_available=settings.is_available,
        reason=None if settings.is_available else settings.unavailable_reason,
    )


@router.get("/password-reset/token-status", response_model=PasswordResetTokenStatusResponse)
def get_password_reset_token_status_route(
    token: str,
    db: Session = Depends(get_db_session),
):
    is_valid, reason = get_password_reset_token_status(db, token=token)
    return PasswordResetTokenStatusResponse(is_valid=is_valid, reason=reason)


@router.post("/password-reset/request", response_model=PasswordActionResponse)
def post_password_reset_request(
    payload: PasswordResetRequest,
    db: Session = Depends(get_db_session),
):
    if not is_setup_complete(db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset is unavailable until setup is complete.",
        )
    try:
        request_password_reset(db, email=payload.email)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return PasswordActionResponse(
        ok=True,
        message=(
            "If we found an active Pantro account with that email, a reset link has been sent."
        ),
    )


@router.post("/password-reset/confirm", response_model=PasswordActionResponse)
def post_password_reset_confirm(
    payload: PasswordResetConfirmRequest,
    db: Session = Depends(get_db_session),
):
    if not is_setup_complete(db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset is unavailable until setup is complete.",
        )
    try:
        confirm_password_reset(db, token=payload.token, password=payload.password)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return PasswordActionResponse(
        ok=True,
        message="Your password has been reset. You can sign in with the new password now.",
    )


@router.post("/password/change", response_model=PasswordActionResponse)
def post_change_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    try:
        change_password(
            db,
            user=current_user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return PasswordActionResponse(ok=True, message="Password updated.")


@router.patch("/profile", response_model=SessionResponse)
def patch_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    try:
        updated_user = update_user_profile(
            db,
            user=current_user,
            email=payload.email,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return build_session_response(updated_user)
