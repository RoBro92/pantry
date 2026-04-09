from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class InstanceSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "instance_settings"
    __table_args__ = (UniqueConstraint("scope_key", name="uq_instance_settings_scope_key"),)

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("isc"), unique=True, nullable=False
    )
    scope_key: Mapped[str] = mapped_column(String(32), nullable=False, default="instance")
    public_base_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    smtp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    smtp_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encrypted_smtp_password: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    smtp_from_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    smtp_from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_test_recipient_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    smtp_security: Mapped[str | None] = mapped_column(String(16), nullable=True)
    smtp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    smtp_last_test_status: Mapped[str] = mapped_column(String(32), nullable=False, default="never")
    smtp_last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    smtp_last_test_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    password_reset_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    password_reset_subject_template: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_reset_body_template: Mapped[str | None] = mapped_column(Text(), nullable=True)
    release_notes_seen_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    release_notes_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
