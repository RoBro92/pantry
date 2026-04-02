from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class ImportJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_jobs"

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("imp"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    source_label: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    occurred_on: Mapped[date | None] = mapped_column(Date(), nullable=True)
    parser_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    line_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    matched_line_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    needs_review_line_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    unresolved_line_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    ignored_line_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    confirmed_line_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)

    household = relationship("Household", back_populates="import_jobs")
    requested_by_user = relationship("User", back_populates="import_jobs_requested")
    source_files = relationship("ImportSourceFile", back_populates="import_job")
    lines = relationship("ImportLine", back_populates="import_job")
