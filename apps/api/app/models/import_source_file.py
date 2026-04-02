from __future__ import annotations

from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class ImportSourceFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_source_files"

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("isf"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    import_job_id: Mapped[UUID] = mapped_column(ForeignKey("import_jobs.id"), nullable=False)
    uploaded_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    client_content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detected_content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_extension: Mapped[str | None] = mapped_column(String(16), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    sha256_hex: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="accepted")
    scan_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_scanned")
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)

    household = relationship("Household", back_populates="import_source_files")
    import_job = relationship("ImportJob", back_populates="source_files")
    uploaded_by_user = relationship("User", back_populates="import_source_files_uploaded")
