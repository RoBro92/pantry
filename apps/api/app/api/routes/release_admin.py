from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps.auth import require_platform_admin
from app.models.user import User
from app.schemas.releases import ReleaseCheckResponse
from app.services.releases import build_release_check_summary

router = APIRouter(prefix="/platform-admin/release-status", tags=["platform-admin-release"])


@router.get("", response_model=ReleaseCheckResponse)
def get_release_status(_: User = Depends(require_platform_admin)):
    return ReleaseCheckResponse.model_validate(build_release_check_summary())
