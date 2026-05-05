from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password, verify_password
from app.models.base import utc_now
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.audit import record_audit_event
from app.services.auth import get_user_by_email, get_user_by_external_id, rotate_user_session_version
from app.services.instance_settings import (
    PASSWORD_RESET_LINK_PLACEHOLDER,
    resolve_password_reset_email_settings,
    resolve_public_base_url,
)
from app.services.smtp import send_email

PASSWORD_RESET_TOKEN_TTL = timedelta(hours=2)


def _as_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def user_has_self_service_reset_email(user: User) -> bool:
    candidate = (user.email or "").strip()
    _, parsed_email = parseaddr(candidate)
    return bool(candidate and parsed_email and "@" in parsed_email)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _mask_reset_tokens(db: Session, *, user: User) -> None:
    now = utc_now()
    outstanding_tokens = db.scalars(
        select(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id)
        .where(PasswordResetToken.used_at.is_(None))
    ).all()
    for token in outstanding_tokens:
        token.used_at = now
        db.add(token)


def _create_password_reset_token(
    db: Session,
    *,
    user: User,
) -> str:
    _mask_reset_tokens(db, user=user)
    raw_token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            expires_at=utc_now() + PASSWORD_RESET_TOKEN_TTL,
        )
    )
    db.flush()
    return raw_token


def _render_template(
    template: str,
    *,
    user: User,
    reset_link: str,
) -> str:
    user_name = (user.display_name or user.email).strip() or "there"
    return (
        template.replace(PASSWORD_RESET_LINK_PLACEHOLDER, reset_link)
        .replace("{{user_name}}", user_name)
        .replace("{{user_identifier}}", user.email)
        .replace("{{app_name}}", "Pantro")
    )


def _build_reset_link(db: Session, *, token: str) -> str:
    public_base_url = resolve_public_base_url(db).effective_value
    return f"{public_base_url}/reset-password?token={quote(token)}"


def request_password_reset(
    db: Session,
    *,
    email: str,
) -> bool:
    settings = resolve_password_reset_email_settings(db)
    if not settings.is_available:
        raise ValueError(settings.unavailable_reason or "Password reset emails are unavailable.")

    user = get_user_by_email(db, email)
    if user is None or not user.is_active or not user_has_self_service_reset_email(user):
        return False

    raw_token = _create_password_reset_token(db, user=user)
    reset_link = _build_reset_link(db, token=raw_token)
    send_email(
        db,
        to_email=user.email,
        subject=_render_template(settings.template.subject, user=user, reset_link=reset_link),
        body=_render_template(settings.template.body_template, user=user, reset_link=reset_link),
    )
    record_audit_event(
        db,
        household=None,
        actor=None,
        action="auth.password_reset_requested",
        target_type="user",
        target_external_id=user.external_id,
        event_metadata={"email": user.email},
    )
    db.commit()
    return True


def get_password_reset_token_status(
    db: Session,
    *,
    token: str,
) -> tuple[bool, str | None]:
    token_record = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == _hash_token(token))
        .options(selectinload(PasswordResetToken.user))
    )
    if token_record is None:
        return False, "This password reset link is invalid."
    if token_record.used_at is not None:
        return False, "This password reset link has already been used."
    if _as_utc_datetime(token_record.expires_at) <= utc_now():
        return False, "This password reset link has expired."
    if token_record.user is None or not token_record.user.is_active:
        return False, "This account can no longer use password reset."
    return True, None


def confirm_password_reset(
    db: Session,
    *,
    token: str,
    password: str,
) -> User:
    if len(password) < 8:
        raise ValueError("Passwords must be at least 8 characters.")

    token_record = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == _hash_token(token))
        .options(selectinload(PasswordResetToken.user))
    )
    if token_record is None:
        raise ValueError("This password reset link is invalid.")
    if token_record.used_at is not None:
        raise ValueError("This password reset link has already been used.")
    if _as_utc_datetime(token_record.expires_at) <= utc_now():
        raise ValueError("This password reset link has expired.")
    if token_record.user is None or not token_record.user.is_active:
        raise ValueError("This account can no longer use password reset.")

    user = token_record.user
    user.password_hash = hash_password(password)
    rotate_user_session_version(user)
    token_record.used_at = utc_now()
    db.add(user)
    db.add(token_record)
    _mask_reset_tokens(db, user=user)
    record_audit_event(
        db,
        household=None,
        actor=None,
        action="auth.password_reset_completed",
        target_type="user",
        target_external_id=user.external_id,
        event_metadata={"email": user.email},
    )
    db.commit()
    return get_user_by_external_id(db, user.external_id) or user


def change_password(
    db: Session,
    *,
    user: User,
    current_password: str,
    new_password: str,
) -> User:
    if not verify_password(current_password, user.password_hash):
        raise ValueError("Your current password is incorrect.")
    if len(new_password) < 8:
        raise ValueError("Passwords must be at least 8 characters.")
    if verify_password(new_password, user.password_hash):
        raise ValueError("Choose a new password that is different from your current one.")

    user.password_hash = hash_password(new_password)
    rotate_user_session_version(user)
    db.add(user)
    _mask_reset_tokens(db, user=user)
    record_audit_event(
        db,
        household=None,
        actor=user,
        action="auth.password_changed",
        target_type="user",
        target_external_id=user.external_id,
        event_metadata={"email": user.email},
    )
    db.commit()
    return get_user_by_external_id(db, user.external_id) or user
