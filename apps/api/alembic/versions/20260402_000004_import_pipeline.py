"""import pipeline foundation

Revision ID: 20260402_000004
Revises: 20260402_000003
Create Date: 2026-04-02 00:00:04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260402_000004"
down_revision = "20260402_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("source_label", sa.String(length=255), nullable=False),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("occurred_on", sa.Date(), nullable=True),
        sa.Column("parser_kind", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.String(length=512), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("needs_review_line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unresolved_line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ignored_line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confirmed_line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_import_jobs_household_id", "import_jobs", ["household_id"])
    op.create_index("ix_import_jobs_status_created_at", "import_jobs", ["status", "created_at"])

    op.create_table(
        "import_source_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("import_job_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("client_content_type", sa.String(length=255), nullable=True),
        sa.Column("detected_content_type", sa.String(length=255), nullable=True),
        sa.Column("file_extension", sa.String(length=16), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256_hex", sa.String(length=64), nullable=False),
        sa.Column("validation_status", sa.String(length=32), nullable=False, server_default="accepted"),
        sa.Column("scan_status", sa.String(length=32), nullable=False, server_default="not_scanned"),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_import_source_files_household_id", "import_source_files", ["household_id"])
    op.create_index("ix_import_source_files_import_job_id", "import_source_files", ["import_job_id"])

    op.create_table(
        "import_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("import_job_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("suggested_product_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_stock_lot_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source_reference", sa.String(length=64), nullable=True),
        sa.Column("raw_label", sa.String(length=255), nullable=False),
        sa.Column("normalized_label", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("barcode", sa.String(length=64), nullable=True),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("purchased_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="needs_review"),
        sa.Column("match_basis", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["confirmed_stock_lot_id"], ["stock_lots.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["suggested_product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_import_lines_household_id", "import_lines", ["household_id"])
    op.create_index("ix_import_lines_import_job_id", "import_lines", ["import_job_id"])
    op.create_index("ix_import_lines_product_id", "import_lines", ["product_id"])
    op.create_index("ix_import_lines_status", "import_lines", ["status"])


def downgrade() -> None:
    op.drop_index("ix_import_lines_status", table_name="import_lines")
    op.drop_index("ix_import_lines_product_id", table_name="import_lines")
    op.drop_index("ix_import_lines_import_job_id", table_name="import_lines")
    op.drop_index("ix_import_lines_household_id", table_name="import_lines")
    op.drop_table("import_lines")
    op.drop_index("ix_import_source_files_import_job_id", table_name="import_source_files")
    op.drop_index("ix_import_source_files_household_id", table_name="import_source_files")
    op.drop_table("import_source_files")
    op.drop_index("ix_import_jobs_status_created_at", table_name="import_jobs")
    op.drop_index("ix_import_jobs_household_id", table_name="import_jobs")
    op.drop_table("import_jobs")
