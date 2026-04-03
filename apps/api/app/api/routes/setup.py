from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.schemas.auth import SessionResponse
from app.schemas.setup import BootstrapPlatformAdminRequest, SetupStatusResponse
from app.services.auth import build_session_response
from app.services.setup import bootstrap_first_platform_admin, get_setup_status

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatusResponse)
def get_status(db: Session = Depends(get_db_session)):
    return get_setup_status(db)


@router.post("/bootstrap-platform-admin", response_model=SessionResponse)
def post_bootstrap_platform_admin(
    payload: BootstrapPlatformAdminRequest,
    request: Request,
    db: Session = Depends(get_db_session),
):
    try:
        user = bootstrap_first_platform_admin(
            db,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    request.session.clear()
    request.session["user_external_id"] = user.external_id
    return build_session_response(user)
