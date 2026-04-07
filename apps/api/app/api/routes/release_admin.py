from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps.auth import require_platform_admin
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.releases import ReleaseCheckResponse
from app.services.releases import build_release_check_summary, mark_current_release_notes_seen

router = APIRouter(prefix="/platform-admin/release-status", tags=["platform-admin-release"])


@router.get("", response_model=ReleaseCheckResponse)
def get_release_status(
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    return ReleaseCheckResponse.model_validate(build_release_check_summary(db))


@router.post("/mark-seen", response_model=ReleaseCheckResponse)
def post_mark_release_notes_seen(
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    return ReleaseCheckResponse.model_validate(mark_current_release_notes_seen(db, actor=current_user))
