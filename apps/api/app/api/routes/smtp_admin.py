from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_platform_admin
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.smtp import SMTPConfigResponse, SMTPConfigUpdateRequest, SMTPTestResponse
from app.services.instance_settings import build_smtp_summary, record_smtp_test_result, upsert_smtp_settings
from app.services.smtp import run_smtp_connectivity_test

router = APIRouter(prefix="/platform-admin/smtp", tags=["platform-admin-smtp"])


def _build_response(db: Session) -> SMTPConfigResponse:
    return SMTPConfigResponse.model_validate(build_smtp_summary(db))


@router.get("", response_model=SMTPConfigResponse)
def get_smtp_config(
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    return _build_response(db)


@router.put("", response_model=SMTPConfigResponse)
def put_smtp_config(
    payload: SMTPConfigUpdateRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_platform_admin),
):
    try:
        upsert_smtp_settings(
            db,
            actor=current_user,
            host=payload.host,
            port=payload.port,
            username=payload.username,
            password=payload.password,
            from_email=payload.from_email,
            from_name=payload.from_name,
            security=payload.security,
            is_enabled=payload.is_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _build_response(db)


@router.post("/test", response_model=SMTPTestResponse)
def post_smtp_test(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_platform_admin),
):
    try:
        result = run_smtp_connectivity_test(db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    record_smtp_test_result(
        db,
        actor=current_user,
        status=result.status,
        error=None if result.ok else result.message,
    )
    return SMTPTestResponse(
        ok=result.ok,
        status=result.status,
        message=result.message,
        config=_build_response(db),
    )
