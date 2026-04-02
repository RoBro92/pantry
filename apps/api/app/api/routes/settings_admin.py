from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_platform_admin
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.settings import PublicBaseURLSummary, PublicBaseURLUpdateRequest
from app.services.instance_settings import build_public_base_url_summary, upsert_public_base_url

router = APIRouter(prefix="/platform-admin/settings", tags=["platform-admin-settings"])


@router.get("/public-base-url", response_model=PublicBaseURLSummary)
def get_public_base_url(
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    return PublicBaseURLSummary.model_validate(build_public_base_url_summary(db))


@router.put("/public-base-url", response_model=PublicBaseURLSummary)
def put_public_base_url(
    payload: PublicBaseURLUpdateRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_platform_admin),
):
    try:
        upsert_public_base_url(db, actor=current_user, public_base_url=payload.public_base_url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return PublicBaseURLSummary.model_validate(build_public_base_url_summary(db))
