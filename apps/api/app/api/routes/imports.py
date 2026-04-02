from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.api.deps.tenancy import require_household_access
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.imports import ConfirmImportRequest, ImportDetailResponse, ImportListResponse, UpdateImportLineRequest
from app.services.import_queries import build_import_detail_response, build_import_list_response
from app.services.import_workflow import confirm_import_job, create_import_upload, update_import_line
from app.services.tenancy import HouseholdAccess

router = APIRouter(prefix="/households/{household_external_id}", tags=["imports"])


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


@router.get("/imports", response_model=ImportListResponse)
def get_imports(
    db: Session = Depends(get_db_session),
    access: HouseholdAccess = Depends(require_household_access()),
):
    return build_import_list_response(db, access=access)


@router.get("/imports/{import_external_id}", response_model=ImportDetailResponse)
def get_import_detail(
    import_external_id: str,
    db: Session = Depends(get_db_session),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        return build_import_detail_response(db, access=access, import_external_id=import_external_id)
    except ValueError as exc:
        if str(exc) == "Import job not found.":
            raise _not_found(str(exc)) from exc
        raise _bad_request(exc) from exc


@router.post("/imports/uploads", response_model=ImportDetailResponse, status_code=status.HTTP_201_CREATED)
async def post_import_upload(
    source_type: str = Form(...),
    occurred_on: date | None = Form(default=None),
    note: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        import_job = await create_import_upload(
            db,
            household=access.household,
            actor=current_user,
            source_type=source_type,
            occurred_on=occurred_on,
            note=note,
            upload=file,
        )
        return build_import_detail_response(db, access=access, import_external_id=import_job.external_id)
    except ValueError as exc:
        db.rollback()
        raise _bad_request(exc) from exc


@router.put("/imports/{import_external_id}/lines/{line_external_id}", response_model=ImportDetailResponse)
def put_import_line(
    import_external_id: str,
    line_external_id: str,
    payload: UpdateImportLineRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        import_job = update_import_line(
            db,
            household=access.household,
            actor=current_user,
            import_external_id=import_external_id,
            line_external_id=line_external_id,
            updates=payload.model_dump(exclude_unset=True),
        )
        return build_import_detail_response(db, access=access, import_external_id=import_job.external_id)
    except ValueError as exc:
        if str(exc) == "Import job not found." or str(exc) == "Import line not found.":
            raise _not_found(str(exc)) from exc
        raise _bad_request(exc) from exc


@router.post("/imports/{import_external_id}/confirm", response_model=ImportDetailResponse)
def post_confirm_import(
    import_external_id: str,
    payload: ConfirmImportRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        import_job = confirm_import_job(
            db,
            household=access.household,
            actor=current_user,
            import_external_id=import_external_id,
            location_external_id=payload.location_external_id,
            purchased_on=payload.purchased_on,
        )
        return build_import_detail_response(db, access=access, import_external_id=import_job.external_id)
    except ValueError as exc:
        if str(exc) == "Import job not found.":
            raise _not_found(str(exc)) from exc
        raise _bad_request(exc) from exc
