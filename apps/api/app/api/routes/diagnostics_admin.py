from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps.auth import require_platform_admin
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.diagnostics import DiagnosticsResponse
from app.services.diagnostics import build_diagnostics_report

router = APIRouter(prefix="/platform-admin/diagnostics", tags=["platform-admin-diagnostics"])


@router.get("", response_model=DiagnosticsResponse)
def get_diagnostics(
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    return DiagnosticsResponse.model_validate(build_diagnostics_report(db))
