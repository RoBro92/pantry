from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_platform_admin
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.smtp import (
    SMTPConfigResponse,
    SMTPConfigUpdateRequest,
    SMTPTemplateUpdateRequest,
    SMTPTestEmailResponse,
    SMTPTestResponse,
)
from app.services.instance_settings import (
    PASSWORD_RESET_TEMPLATE_KEY,
    build_smtp_summary,
    get_or_create_instance_settings,
    record_smtp_test_result,
    restore_default_password_reset_email_template,
    upsert_password_reset_email_template,
    upsert_smtp_settings,
)
from app.services.smtp import run_smtp_connectivity_test, send_smtp_test_email
from app.services.audit import record_audit_event

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
            test_recipient_email=payload.test_recipient_email,
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


@router.post("/test-email", response_model=SMTPTestEmailResponse)
def post_smtp_test_email(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_platform_admin),
):
    try:
        delivered_to = send_smtp_test_email(db)
        settings = get_or_create_instance_settings(db)
        record_audit_event(
            db,
            household=None,
            actor=current_user,
            action="smtp.test_email.sent",
            target_type="instance_setting",
            target_external_id=settings.external_id,
            event_metadata={"delivered_to": delivered_to},
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return SMTPTestEmailResponse(
        ok=True,
        message="SMTP test email sent.",
        delivered_to=delivered_to,
        config=_build_response(db),
    )


@router.put("/templates/{template_key}", response_model=SMTPConfigResponse)
def put_smtp_template(
    template_key: str,
    payload: SMTPTemplateUpdateRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_platform_admin),
):
    if template_key != PASSWORD_RESET_TEMPLATE_KEY:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMTP template not found.")
    try:
        upsert_password_reset_email_template(
            db,
            actor=current_user,
            is_enabled=payload.is_enabled,
            subject=payload.subject,
            body_template=payload.body_template,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _build_response(db)


@router.post("/templates/{template_key}/restore-default", response_model=SMTPConfigResponse)
def post_restore_smtp_template_default(
    template_key: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_platform_admin),
):
    if template_key != PASSWORD_RESET_TEMPLATE_KEY:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMTP template not found.")
    restore_default_password_reset_email_template(db, actor=current_user)
    return _build_response(db)
