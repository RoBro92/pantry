from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.auth import LoginRequest, LogoutResponse, SessionResponse
from app.services.auth import authenticate_user, build_session_response

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db_session)):
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    request.session.clear()
    request.session["user_external_id"] = user.external_id
    return build_session_response(user)


@router.post("/logout", response_model=LogoutResponse)
def logout(request: Request, _: User = Depends(get_current_user)):
    request.session.clear()
    return LogoutResponse(ok=True)


@router.get("/session", response_model=SessionResponse)
def current_session(response: Response, request: Request, current_user: User = Depends(get_current_user)):
    response.headers["cache-control"] = "no-store"
    request.session["user_external_id"] = current_user.external_id
    return build_session_response(current_user)

