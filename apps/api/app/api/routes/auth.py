from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.config import get_settings
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
from app.services.rate_limits import check_rate_limit, clear_rate_limit, hit_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])
LOGIN_LIMIT_MESSAGE = "Too many authentication attempts. Please wait before trying again."
PASSWORD_RESET_LIMIT_MESSAGE = "Too many password reset requests. Please wait before trying again."


def _client_scope(request: Request) -> str:
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


def _store_user_session(request: Request, user: User) -> None:
    request.session.clear()
    request.session["user_external_id"] = user.external_id
    request.session["session_version"] = user.session_version


def _reject_limited(message: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=message,
    )


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db_session)):
    if not is_setup_complete(db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pantro setup is not complete yet. Finish the setup wizard first.",
        )

    identifier = payload.identifier or payload.email or ""
    settings = get_settings()
    client_scope = _client_scope(request)
    ip_limit = check_rate_limit(
        "login:ip",
        client_scope,
        limit=settings.login_rate_limit_attempts,
        window_seconds=settings.login_rate_limit_window_seconds,
    )
    identifier_limit = check_rate_limit(
        "login:identifier",
        identifier,
        limit=settings.login_rate_limit_attempts,
        window_seconds=settings.login_rate_limit_window_seconds,
    )
    if not ip_limit.allowed or not identifier_limit.allowed:
        _reject_limited(LOGIN_LIMIT_MESSAGE)

    user = authenticate_user(db, identifier, payload.password)
    if user is None:
        ip_limit = hit_rate_limit(
            "login:ip",
            client_scope,
            limit=settings.login_rate_limit_attempts,
            window_seconds=settings.login_rate_limit_window_seconds,
        )
        identifier_limit = hit_rate_limit(
            "login:identifier",
            identifier,
            limit=settings.login_rate_limit_attempts,
            window_seconds=settings.login_rate_limit_window_seconds,
        )
        if not ip_limit.allowed or not identifier_limit.allowed:
            _reject_limited(LOGIN_LIMIT_MESSAGE)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

    clear_rate_limit("login:identifier", identifier)
    _store_user_session(request, user)
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
    request.session["session_version"] = current_user.session_version
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
    request: Request,
    db: Session = Depends(get_db_session),
):
    if not is_setup_complete(db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset is unavailable until setup is complete.",
        )
    settings = get_settings()
    ip_limit = hit_rate_limit(
        "password-reset:ip",
        _client_scope(request),
        limit=settings.password_reset_rate_limit_attempts,
        window_seconds=settings.password_reset_rate_limit_window_seconds,
    )
    identifier_limit = hit_rate_limit(
        "password-reset:identifier",
        payload.email,
        limit=settings.password_reset_rate_limit_attempts,
        window_seconds=settings.password_reset_rate_limit_window_seconds,
    )
    if not ip_limit.allowed or not identifier_limit.allowed:
        _reject_limited(PASSWORD_RESET_LIMIT_MESSAGE)

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
    request: Request,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    try:
        updated_user = change_password(
            db,
            user=current_user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    _store_user_session(request, updated_user)
    return PasswordActionResponse(ok=True, message="Password updated.")


@router.patch("/profile", response_model=SessionResponse)
def patch_profile(
    payload: ProfileUpdateRequest,
    request: Request,
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

    _store_user_session(request, updated_user)
    return build_session_response(updated_user)
