from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("usr"), unique=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    platform_role_id: Mapped[UUID | None] = mapped_column(ForeignKey("roles.id"), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dietary_preferences: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    session_version: Mapped[int] = mapped_column(Integer(), nullable=False, default=0, server_default="0")

    platform_role = relationship("Role")
    memberships = relationship("Membership", back_populates="user")
    audit_events = relationship("AuditEvent", back_populates="actor_user")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user")
    recipe_url_imports_requested = relationship("RecipeURLImport", back_populates="requested_by_user")
    import_jobs_requested = relationship("ImportJob", back_populates="requested_by_user")
    product_intelligence_runs_requested = relationship("ProductIntelligenceRun", back_populates="requested_by_user")
    import_source_files_uploaded = relationship("ImportSourceFile", back_populates="uploaded_by_user")
