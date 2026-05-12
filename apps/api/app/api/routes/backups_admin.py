from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps.auth import require_platform_admin
from app.core.config import get_settings
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.backups import (
    BackupRestoreRequest,
    BackupRestoreResponse,
    BackupBundleSummary,
    StagedBackupResponse,
)
from app.services.backups import (
    RESTORE_CONFIRMATION_PHRASE,
    backup_bundle_to_json,
    backup_download_filename,
    build_household_backup_bundle,
    build_instance_backup_bundle,
    bundle_summary,
    clear_staged_backup,
    load_staged_backup,
    restore_instance_backup_bundle,
    stage_backup_upload,
)

router = APIRouter(prefix="/platform-admin/backups", tags=["platform-admin-backups"])


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _download_response(bundle: dict[str, object]) -> Response:
    summary = bundle_summary(bundle)
    filename = backup_download_filename(
        scope=str(summary["scope"]),
        exported_at=summary["exported_at"],
        household_name=summary.get("household_name"),
    )
    return Response(
        content=backup_bundle_to_json(bundle),
        media_type="application/json",
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/instance")
def get_instance_backup_export(
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    return _download_response(build_instance_backup_bundle(db))


@router.get("/export/households/{household_external_id}")
def get_household_backup_export(
    household_external_id: str,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    try:
        bundle = build_household_backup_bundle(db, household_external_id=household_external_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return _download_response(bundle)


@router.post("/restore-upload", response_model=StagedBackupResponse)
async def post_restore_upload(
    file: UploadFile = File(...),
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    try:
        staged = await stage_backup_upload(
            db,
            settings=get_settings(),
            upload=file,
            allowed_restore_scopes={"instance"},
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return StagedBackupResponse(
        stage_id=staged.stage_id,
        original_filename=staged.original_filename,
        size_bytes=staged.size_bytes,
        uploaded_at=staged.uploaded_at,
        quarantine_path=staged.quarantine_path,
        supported_for_restore=staged.supported_for_restore,
        warnings=list(staged.warnings),
        bundle=BackupBundleSummary.model_validate(bundle_summary(staged.bundle)),
    )


@router.post("/restore", response_model=BackupRestoreResponse)
def post_restore_backup(
    payload: BackupRestoreRequest,
    request: Request,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    if payload.confirmation_phrase.strip() != RESTORE_CONFIRMATION_PHRASE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Enter the exact confirmation phrase: {RESTORE_CONFIRMATION_PHRASE}",
        )

    try:
        bundle = load_staged_backup(get_settings(), stage_id=payload.stage_id)
        restored_bundle = restore_instance_backup_bundle(
            db,
            bundle=bundle,
            actor_external_id=current_user.external_id,
        )
        clear_staged_backup(get_settings(), stage_id=payload.stage_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc

    request.session.clear()
    return BackupRestoreResponse(
        restored=True,
        requires_reauthentication=True,
        message="Backup restored. Sign in again to continue with the restored data set.",
        bundle=BackupBundleSummary.model_validate(restored_bundle),
    )
