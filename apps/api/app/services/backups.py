from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Numeric, Uuid, delete, func, select, text
from sqlalchemy.orm import Session

from app.core.security import normalize_email
from app.core.config import AppSettings, get_settings
from app.models.base import Base
from app.models.household import Household
from app.models.membership import Membership
from app.models.role import Role
from app.models.user import User
from app.models.identifiers import generate_external_id
from app.services.audit import record_audit_event
from app.services.import_storage import sanitize_upload_filename

if TYPE_CHECKING:
    from fastapi import UploadFile

BACKUP_FORMAT = "pantry.backup.bundle"
BACKUP_FORMAT_VERSION = 1
ALLOWED_BACKUP_EXTENSIONS = {".json"}
RESTORE_CONFIRMATION_PHRASE = "RESTORE PANTRY INSTANCE"
HOUSEHOLD_RESTORE_CONFIRMATION_PHRASE = "RESTORE PANTRY HOUSEHOLD"
HOUSEHOLD_EXPORT_TABLES = {
    "roles",
    "users",
    "households",
    "memberships",
    "location_groups",
    "locations",
    "products",
    "product_enrichments",
    "product_aliases",
    "barcodes",
    "stock_lots",
    "shopping_lists",
    "shopping_list_items",
    "recipes",
    "recipe_ingredients",
    "recipe_url_imports",
    "import_jobs",
    "import_source_files",
    "import_lines",
    "ai_provider_configs",
    "audit_events",
}
HOUSEHOLD_RESTORE_SKIPPED_TABLES = frozenset({"audit_events", "import_source_files"})
TABLE_EXTERNAL_ID_PREFIXES = {
    "users": "usr",
    "households": "hse",
    "memberships": "mem",
    "location_groups": "lgr",
    "locations": "loc",
    "products": "prd",
    "product_aliases": "pal",
    "barcodes": "brc",
    "stock_lots": "lot",
    "shopping_lists": "shl",
    "shopping_list_items": "sli",
    "recipes": "rcp",
    "recipe_ingredients": "rci",
    "recipe_url_imports": "rim",
    "import_jobs": "imp",
    "import_source_files": "isf",
    "import_lines": "iml",
    "ai_provider_configs": "aic",
    "audit_events": "evt",
    "product_enrichments": "pen",
}


@dataclass(frozen=True)
class StagedBackupUpload:
    stage_id: str
    original_filename: str
    size_bytes: int
    uploaded_at: datetime
    quarantine_path: str
    bundle: dict[str, Any]
    supported_for_restore: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RestoreCompatibility:
    supported: bool
    allowed_missing_tables: frozenset[str]
    warnings: tuple[str, ...]


_SCHEMA_COMPATIBILITY: dict[tuple[str | None, str | None], RestoreCompatibility] = {
    (
        "20260412_000019",
        "20260410_000018",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"product_intelligence_runs"}),
        warnings=(
            "This backup predates product intelligence run history support. Background classification run history will restore as empty.",
        ),
    ),
    (
        "20260412_000019",
        "20260409_000017",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"product_intelligence_records", "product_intelligence_runs"}),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
            "This backup predates product intelligence run history support. Background classification run history will restore as empty.",
        ),
    ),
    (
        "20260412_000019",
        "20260409_000016",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"product_intelligence_records", "product_intelligence_runs"}),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
            "This backup predates product intelligence run history support. Background classification run history will restore as empty.",
        ),
    ),
    (
        "20260412_000019",
        "20260409_000015",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"product_intelligence_records", "product_intelligence_runs"}),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
            "This backup predates product intelligence run history support. Background classification run history will restore as empty.",
        ),
    ),
    (
        "20260412_000019",
        "20260409_000014",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"product_intelligence_records", "product_intelligence_runs"}),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
            "This backup predates product intelligence run history support. Background classification run history will restore as empty.",
        ),
    ),
    (
        "20260412_000019",
        "20260408_000013",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(
            {"product_intelligence_records", "product_intelligence_runs", "password_reset_tokens"}
        ),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
            "This backup predates product intelligence run history support. Background classification run history will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260412_000019",
        "20260408_000012",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(
            {"product_intelligence_records", "product_intelligence_runs", "password_reset_tokens"}
        ),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
            "This backup predates product intelligence run history support. Background classification run history will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260412_000019",
        "20260408_000011",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(
            {"product_intelligence_records", "product_intelligence_runs", "password_reset_tokens"}
        ),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
            "This backup predates product intelligence run history support. Background classification run history will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260412_000019",
        "20260407_000010",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(
            {
                "product_intelligence_records",
                "product_intelligence_runs",
                "shopping_lists",
                "shopping_list_items",
                "password_reset_tokens",
            }
        ),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
            "This backup predates product intelligence run history support. Background classification run history will restore as empty.",
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260412_000019",
        "20260407_000009",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(
            {
                "product_intelligence_records",
                "product_intelligence_runs",
                "product_enrichments",
                "shopping_lists",
                "shopping_list_items",
                "password_reset_tokens",
            }
        ),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
            "This backup predates product intelligence run history support. Background classification run history will restore as empty.",
            "This backup predates product enrichment support. Product enrichment records will restore as empty.",
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260410_000018",
        "20260409_000017",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"product_intelligence_records"}),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
        ),
    ),
    (
        "20260410_000018",
        "20260409_000016",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"product_intelligence_records"}),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
        ),
    ),
    (
        "20260410_000018",
        "20260409_000015",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"product_intelligence_records"}),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
        ),
    ),
    (
        "20260410_000018",
        "20260409_000014",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"product_intelligence_records"}),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
        ),
    ),
    (
        "20260410_000018",
        "20260408_000013",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"product_intelligence_records", "password_reset_tokens"}),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260410_000018",
        "20260408_000012",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"product_intelligence_records", "password_reset_tokens"}),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260410_000018",
        "20260408_000011",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"product_intelligence_records", "password_reset_tokens"}),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260410_000018",
        "20260407_000010",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(
            {"product_intelligence_records", "shopping_lists", "shopping_list_items", "password_reset_tokens"}
        ),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260410_000018",
        "20260407_000009",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(
            {
                "product_intelligence_records",
                "product_enrichments",
                "shopping_lists",
                "shopping_list_items",
                "password_reset_tokens",
            }
        ),
        warnings=(
            "This backup predates product intelligence support. Product intelligence records will restore as empty.",
            "This backup predates product enrichment support. Product enrichment records will restore as empty.",
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260409_000016",
        "20260409_000015",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(),
        warnings=(),
    ),
    (
        "20260409_000016",
        "20260409_000014",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(),
        warnings=(),
    ),
    (
        "20260409_000016",
        "20260408_000013",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"password_reset_tokens"}),
        warnings=(
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260409_000016",
        "20260408_000012",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"password_reset_tokens"}),
        warnings=(
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260409_000016",
        "20260408_000011",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"password_reset_tokens"}),
        warnings=(
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260409_000016",
        "20260407_000010",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"shopping_lists", "shopping_list_items", "password_reset_tokens"}),
        warnings=(
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260409_000016",
        "20260407_000009",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(
            {"product_enrichments", "shopping_lists", "shopping_list_items", "password_reset_tokens"}
        ),
        warnings=(
            "This backup predates product enrichment support. Product enrichment records will restore as empty.",
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260409_000015",
        "20260409_000014",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(),
        warnings=(),
    ),
    (
        "20260409_000015",
        "20260408_000013",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(),
        warnings=(),
    ),
    (
        "20260409_000015",
        "20260408_000012",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"password_reset_tokens"}),
        warnings=(
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260409_000015",
        "20260408_000011",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"password_reset_tokens"}),
        warnings=(
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260409_000015",
        "20260407_000010",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"shopping_lists", "shopping_list_items", "password_reset_tokens"}),
        warnings=(
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260409_000015",
        "20260407_000009",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(
            {"product_enrichments", "shopping_lists", "shopping_list_items", "password_reset_tokens"}
        ),
        warnings=(
            "This backup predates product enrichment support. Product enrichment records will restore as empty.",
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260409_000014",
        "20260408_000013",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(),
        warnings=(),
    ),
    (
        "20260409_000014",
        "20260408_000012",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"password_reset_tokens"}),
        warnings=(
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260409_000014",
        "20260408_000011",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"password_reset_tokens"}),
        warnings=(
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260409_000014",
        "20260407_000010",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"shopping_lists", "shopping_list_items", "password_reset_tokens"}),
        warnings=(
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260409_000014",
        "20260407_000009",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(
            {"product_enrichments", "shopping_lists", "shopping_list_items", "password_reset_tokens"}
        ),
        warnings=(
            "This backup predates product enrichment support. Product enrichment records will restore as empty.",
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260408_000013",
        "20260408_000012",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"password_reset_tokens"}),
        warnings=(
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260408_000013",
        "20260408_000011",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"password_reset_tokens"}),
        warnings=(
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260408_000013",
        "20260407_000010",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"shopping_lists", "shopping_list_items", "password_reset_tokens"}),
        warnings=(
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260408_000013",
        "20260407_000009",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(
            {"product_enrichments", "shopping_lists", "shopping_list_items", "password_reset_tokens"}
        ),
        warnings=(
            "This backup predates product enrichment support. Product enrichment records will restore as empty.",
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260408_000012",
        "20260408_000011",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"password_reset_tokens"}),
        warnings=(
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260408_000012",
        "20260407_000010",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"shopping_lists", "shopping_list_items", "password_reset_tokens"}),
        warnings=(
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260408_000012",
        "20260407_000009",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset(
            {"product_enrichments", "shopping_lists", "shopping_list_items", "password_reset_tokens"}
        ),
        warnings=(
            "This backup predates product enrichment support. Product enrichment records will restore as empty.",
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
            "This backup predates password reset token support. Existing reset tokens will restore as empty.",
        ),
    ),
    (
        "20260408_000011",
        "20260407_000010",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"shopping_lists", "shopping_list_items"}),
        warnings=(
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
        ),
    ),
    (
        "20260408_000011",
        "20260407_000009",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"product_enrichments", "shopping_lists", "shopping_list_items"}),
        warnings=(
            "This backup predates product enrichment support. Product enrichment records will restore as empty.",
            "This backup predates shopping list foundations. Shopping list records will restore as empty.",
        ),
    ),
    (
        "20260407_000010",
        "20260407_000009",
    ): RestoreCompatibility(
        supported=True,
        allowed_missing_tables=frozenset({"product_enrichments"}),
        warnings=(
            "This backup predates product enrichment support. Product enrichment records will restore as empty.",
        ),
    ),
}

# Revisions listed here keep the same backup table layout and restore compatibility
# behaviour as the mapped baseline revision.
_SCHEMA_COMPATIBILITY_ALIASES: dict[str, str] = {
    "20260409_000017": "20260409_000016",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _current_schema_revision(db: Session) -> str | None:
    return db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()


def _serialize_scalar(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, list):
        return [_serialize_scalar(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_scalar(item) for key, item in value.items()}
    return value


def _deserialize_scalar(column, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(column.type, Uuid):
        return UUID(str(value))
    if isinstance(column.type, DateTime):
        return datetime.fromisoformat(str(value))
    if isinstance(column.type, Date):
        return date.fromisoformat(str(value))
    if isinstance(column.type, Numeric):
        return Decimal(str(value))
    return value


def _serialize_rows(db: Session, table, statement) -> list[dict[str, Any]]:
    rows = db.execute(statement).mappings().all()
    serialized: list[dict[str, Any]] = []
    for row in rows:
        serialized.append({column.name: _serialize_scalar(row[column.name]) for column in table.columns})
    return serialized


def _table_statement(table):
    primary_key_columns = list(table.primary_key.columns)
    statement = select(table)
    if primary_key_columns:
        statement = statement.order_by(*primary_key_columns)
    return statement


def _full_backup_tables(db: Session) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for table in Base.metadata.sorted_tables:
        tables[table.name] = _serialize_rows(db, table, _table_statement(table))
    return tables


def _household_backup_tables(db: Session, *, household: Household) -> dict[str, list[dict[str, Any]]]:
    memberships_table = Base.metadata.tables["memberships"]
    membership_statement = _table_statement(memberships_table).where(
        memberships_table.c.household_id == household.id
    )
    raw_membership_rows = db.execute(membership_statement).mappings().all()
    membership_rows = [
        {column.name: _serialize_scalar(row[column.name]) for column in memberships_table.columns}
        for row in raw_membership_rows
    ]
    user_ids = [row["user_id"] for row in raw_membership_rows]

    tables: dict[str, list[dict[str, Any]]] = {}
    for table in Base.metadata.sorted_tables:
        if table.name not in HOUSEHOLD_EXPORT_TABLES:
            continue
        if table.name == "roles":
            tables[table.name] = _serialize_rows(db, table, _table_statement(table))
            continue
        if table.name == "households":
            tables[table.name] = _serialize_rows(
                db,
                table,
                _table_statement(table).where(table.c.id == household.id),
            )
            continue
        if table.name == "memberships":
            tables[table.name] = membership_rows
            continue
        if table.name == "users":
            tables[table.name] = (
                _serialize_rows(
                    db,
                    table,
                    _table_statement(table).where(table.c.id.in_(user_ids)),
                )
                if user_ids
                else []
            )
            continue
        if "household_id" in table.c:
            tables[table.name] = _serialize_rows(
                db,
                table,
                _table_statement(table).where(table.c.household_id == household.id),
            )
            continue
        tables[table.name] = []

    return tables


def _bundle_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    metadata = bundle.get("metadata") or {}
    return {
        "format": bundle["format"],
        "format_version": bundle["format_version"],
        "scope": bundle["scope"],
        "app_version": bundle["app_version"],
        "schema_revision": bundle.get("schema_revision"),
        "exported_at": datetime.fromisoformat(str(bundle["exported_at"])),
        "household_external_id": metadata.get("household_external_id"),
        "household_name": metadata.get("household_name"),
        "table_counts": {
            table_name: len(rows)
            for table_name, rows in (bundle.get("tables") or {}).items()
            if isinstance(rows, list)
        },
    }


def _deserialize_table_rows(bundle: dict[str, Any], *, table_name: str) -> list[dict[str, Any]]:
    table = Base.metadata.tables[table_name]
    rows = bundle.get("tables", {}).get(table_name) or []
    deserialized_rows: list[dict[str, Any]] = []
    for row in rows:
        deserialized_rows.append(
            {
                column.name: _deserialize_scalar(column, row[column.name])
                for column in table.columns
                if column.name in row
            }
        )
    return deserialized_rows


def _restore_scope_description(allowed_restore_scopes: set[str]) -> str:
    if allowed_restore_scopes == {"instance"}:
        return "Restore currently supports full instance Pantry backup bundles only."
    if allowed_restore_scopes == {"household"}:
        return "Restore currently supports Pantry household backup bundles only."
    if allowed_restore_scopes == {"household", "instance"}:
        return "Restore supports Pantry full instance and household backup bundles through dedicated flows."
    scopes = ", ".join(sorted(allowed_restore_scopes))
    return f"Restore supports Pantry backup bundles for these scopes: {scopes}."


def _validate_bundle_layout(
    *,
    payload: dict[str, Any],
    expected_tables: set[str],
    allowed_missing_tables: frozenset[str],
) -> None:
    actual_tables = set((payload.get("tables") or {}).keys())
    missing_tables = expected_tables - actual_tables
    unexpected_tables = actual_tables - expected_tables
    disallowed_missing_tables = missing_tables - allowed_missing_tables
    if disallowed_missing_tables or unexpected_tables:
        missing_table_names = sorted(disallowed_missing_tables)
        unexpected_table_names = sorted(unexpected_tables)
        details: list[str] = []
        if missing_table_names:
            details.append(f"missing tables: {', '.join(missing_table_names)}")
        if unexpected_table_names:
            details.append(f"unexpected tables: {', '.join(unexpected_table_names)}")
        suffix = f" ({'; '.join(details)})" if details else ""
        raise ValueError(f"Backup table layout does not match the running Pantry schema.{suffix}")


def _validate_bundle_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("format") != BACKUP_FORMAT:
        raise ValueError("Unsupported backup format. Pantry restore only accepts Pantry backup bundle v1 JSON files.")
    if payload.get("format_version") != BACKUP_FORMAT_VERSION:
        raise ValueError("Unsupported backup format version.")
    if payload.get("scope") not in {"instance", "household"}:
        raise ValueError("Backup bundle scope must be instance or household.")
    if not payload.get("app_version"):
        raise ValueError("Backup bundle is missing the exporting app version.")
    if not payload.get("exported_at"):
        raise ValueError("Backup bundle is missing the export timestamp.")

    tables = payload.get("tables")
    if not isinstance(tables, dict) or not tables:
        raise ValueError("Backup bundle did not include any table data.")

    for table_name, rows in tables.items():
        if table_name not in Base.metadata.tables:
            raise ValueError(f"Backup bundle references unsupported table {table_name}.")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"Backup bundle table {table_name} has invalid row data.")

    return payload


def _restore_compatibility(*, current_revision: str | None, bundle_revision: str | None) -> RestoreCompatibility:
    normalized_current_revision = _SCHEMA_COMPATIBILITY_ALIASES.get(
        current_revision, current_revision
    )
    normalized_bundle_revision = _SCHEMA_COMPATIBILITY_ALIASES.get(
        bundle_revision, bundle_revision
    )

    if normalized_current_revision == normalized_bundle_revision:
        return RestoreCompatibility(
            supported=True,
            allowed_missing_tables=frozenset(),
            warnings=(),
        )
    return _SCHEMA_COMPATIBILITY.get(
        (normalized_current_revision, normalized_bundle_revision),
        RestoreCompatibility(
            supported=False,
            allowed_missing_tables=frozenset(),
            warnings=(),
        ),
    )


def _validate_restore_bundle(db: Session, bundle: dict[str, Any]) -> None:
    payload = _validate_bundle_payload(bundle)
    if payload["scope"] != "instance":
        raise ValueError("Only full instance Pantry backups can be restored in this milestone.")

    current_revision = _current_schema_revision(db)
    bundle_revision = payload.get("schema_revision")
    compatibility = _restore_compatibility(current_revision=current_revision, bundle_revision=bundle_revision)
    if not compatibility.supported:
        raise ValueError(
            "Backup schema revision does not match the running Pantry schema, and this older revision is not marked restore-compatible."
        )

    _validate_bundle_layout(
        payload=payload,
        expected_tables={table.name for table in Base.metadata.sorted_tables},
        allowed_missing_tables=compatibility.allowed_missing_tables,
    )

    roles_rows = payload["tables"].get("roles") or []
    users_rows = payload["tables"].get("users") or []
    platform_role_ids = {
        row.get("id")
        for row in roles_rows
        if row.get("code") == "platform_admin" and row.get("id")
    }
    if not any(user.get("platform_role_id") in platform_role_ids for user in users_rows):
        raise ValueError("Backup bundle must contain at least one platform admin user to restore safely.")


def _validate_household_restore_bundle(db: Session, bundle: dict[str, Any]) -> tuple[RestoreCompatibility, dict[str, Any]]:
    payload = _validate_bundle_payload(bundle)
    if payload["scope"] != "household":
        raise ValueError("Only Pantry household backup bundles can be restored through this flow.")

    current_revision = _current_schema_revision(db)
    bundle_revision = payload.get("schema_revision")
    compatibility = _restore_compatibility(current_revision=current_revision, bundle_revision=bundle_revision)
    if not compatibility.supported:
        raise ValueError(
            "Backup schema revision does not match the running Pantry schema, and this older revision is not marked restore-compatible."
        )

    _validate_bundle_layout(
        payload=payload,
        expected_tables=set(HOUSEHOLD_EXPORT_TABLES),
        allowed_missing_tables=compatibility.allowed_missing_tables,
    )

    household_rows = _deserialize_table_rows(payload, table_name="households")
    if len(household_rows) != 1:
        raise ValueError("Pantry household restore requires exactly one household record in the backup bundle.")

    return compatibility, household_rows[0]


def build_instance_backup_bundle(db: Session) -> dict[str, Any]:
    settings = get_settings()
    return {
        "format": BACKUP_FORMAT,
        "format_version": BACKUP_FORMAT_VERSION,
        "scope": "instance",
        "app_version": settings.app_version,
        "schema_revision": _current_schema_revision(db),
        "exported_at": _utc_now().isoformat(),
        "metadata": {},
        "tables": _full_backup_tables(db),
    }


def build_household_backup_bundle(db: Session, *, household_external_id: str) -> dict[str, Any]:
    settings = get_settings()
    household = db.scalar(select(Household).where(Household.external_id == household_external_id))
    if household is None:
        raise ValueError("Household not found.")

    return {
        "format": BACKUP_FORMAT,
        "format_version": BACKUP_FORMAT_VERSION,
        "scope": "household",
        "app_version": settings.app_version,
        "schema_revision": _current_schema_revision(db),
        "exported_at": _utc_now().isoformat(),
        "metadata": {
            "household_external_id": household.external_id,
            "household_name": household.name,
        },
        "tables": _household_backup_tables(db, household=household),
    }


def backup_download_filename(*, scope: str, exported_at: datetime, household_name: str | None = None) -> str:
    stamp = exported_at.strftime("%Y%m%d-%H%M%S")
    if scope == "household" and household_name:
        normalized_name = "-".join(household_name.lower().split())
        return f"pantry-household-{normalized_name}-{stamp}.json"
    return f"pantry-instance-backup-{stamp}.json"


def backup_bundle_to_json(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, indent=2, sort_keys=True)


def _quarantine_dir(settings: AppSettings) -> Path:
    path = Path(settings.backup_storage_root) / "quarantine"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _staged_backup_path(settings: AppSettings, stage_id: str) -> Path:
    return _quarantine_dir(settings) / f"{stage_id}.json"


async def stage_backup_upload(
    db: Session,
    *,
    settings: AppSettings,
    upload: "UploadFile",
    allowed_restore_scopes: set[str],
) -> StagedBackupUpload:
    original_filename = sanitize_upload_filename(upload.filename)
    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_BACKUP_EXTENSIONS:
        raise ValueError("Unsupported restore file type. Pantry restore only accepts .json backup bundles.")

    data = await upload.read(settings.backup_max_upload_bytes + 1)
    if len(data) > settings.backup_max_upload_bytes:
        raise ValueError("Restore upload exceeds the configured size limit.")

    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Restore upload must be UTF-8 JSON text.") from exc

    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError("Restore upload must be valid Pantry backup JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Restore upload must be a Pantry backup JSON object.")

    bundle = _validate_bundle_payload(payload)
    warnings: list[str] = [
        "Uploaded restore bundles are staged in quarantine and never executed as code.",
        _restore_scope_description(allowed_restore_scopes),
    ]

    current_revision = _current_schema_revision(db)
    compatibility = _restore_compatibility(
        current_revision=current_revision,
        bundle_revision=bundle.get("schema_revision"),
    )
    supported_for_restore = compatibility.supported
    if bundle["scope"] not in allowed_restore_scopes:
        supported_for_restore = False
        warnings.append("This backup scope can be exported, but it is not restorable through this flow.")
    if not compatibility.supported:
        warnings.append(
            "This backup was created from a different Pantry schema revision, and this version gap is not restore-compatible yet."
        )
    else:
        warnings.extend(compatibility.warnings)
    if bundle["scope"] == "household" and "household" in allowed_restore_scopes:
        warnings.append(
            "Household restore creates a brand new household only. Pantry does not merge household backup data into an existing household."
        )
        warnings.append(
            "Historical household audit events and original import upload blobs are not replayed during household restore."
        )

    stage_id = secrets.token_hex(16)
    uploaded_at = _utc_now()
    staged_path = _staged_backup_path(settings, stage_id)
    staged_path.write_bytes(data)

    return StagedBackupUpload(
        stage_id=stage_id,
        original_filename=original_filename,
        size_bytes=len(data),
        uploaded_at=uploaded_at,
        quarantine_path=str(staged_path.relative_to(Path(settings.backup_storage_root))),
        bundle=bundle,
        supported_for_restore=supported_for_restore,
        warnings=tuple(warnings),
    )


def load_staged_backup(settings: AppSettings, *, stage_id: str) -> dict[str, Any]:
    staged_path = _staged_backup_path(settings, stage_id)
    if not staged_path.exists():
        raise ValueError("The staged restore file could not be found.")

    payload = json.loads(staged_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("The staged restore file is invalid.")
    return _validate_bundle_payload(payload)


def clear_staged_backup(settings: AppSettings, *, stage_id: str) -> None:
    staged_path = _staged_backup_path(settings, stage_id)
    try:
        staged_path.unlink()
    except FileNotFoundError:
        return


def restore_instance_backup_bundle(
    db: Session,
    *,
    bundle: dict[str, Any],
    actor_external_id: str | None,
) -> dict[str, Any]:
    _validate_restore_bundle(db, bundle)

    tables_payload = bundle["tables"]
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))

        for table in Base.metadata.sorted_tables:
            rows = tables_payload.get(table.name) or []
            if not rows:
                continue
            deserialized_rows = []
            for row in rows:
                deserialized_rows.append(
                    {
                        column.name: _deserialize_scalar(column, row[column.name])
                        for column in table.columns
                        if column.name in row
                    }
                )
            db.execute(table.insert(), deserialized_rows)

        actor = db.scalar(select(User).where(User.external_id == actor_external_id)) if actor_external_id else None
        record_audit_event(
            db,
            household=None,
            actor=actor,
            action="admin.backup.restored",
            target_type="backup_bundle",
            target_external_id=str(bundle["exported_at"]),
            event_metadata={
                "format": bundle["format"],
                "format_version": bundle["format_version"],
                "scope": bundle["scope"],
                "app_version": bundle["app_version"],
                "schema_revision": bundle.get("schema_revision"),
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return _bundle_summary(bundle)


def _new_record_identity(table_name: str) -> tuple[UUID, str]:
    prefix = TABLE_EXTERNAL_ID_PREFIXES.get(table_name)
    if prefix is None:
        raise ValueError(f"No external ID prefix is registered for {table_name}.")
    return uuid4(), generate_external_id(prefix)


def _copy_row_for_household_restore(
    row: dict[str, Any],
    *,
    table_name: str,
    household_id: UUID,
) -> dict[str, Any]:
    copied = dict(row)
    copied["household_id"] = household_id
    new_id, new_external_id = _new_record_identity(table_name)
    copied["id"] = new_id
    copied["external_id"] = new_external_id
    return copied


def _build_role_id_map(db: Session, *, bundle: dict[str, Any]) -> dict[UUID, UUID]:
    current_roles = {
        role.code: role.id
        for role in db.scalars(select(Role).order_by(Role.code)).all()
    }
    role_id_map: dict[UUID, UUID] = {}
    for row in _deserialize_table_rows(bundle, table_name="roles"):
        role_code = str(row.get("code") or "").strip()
        role_id = row.get("id")
        if not role_code or not isinstance(role_id, UUID):
            continue
        current_role_id = current_roles.get(role_code)
        if current_role_id is None:
            raise ValueError(f"Backup bundle references unknown role code {role_code}.")
        role_id_map[role_id] = current_role_id
    return role_id_map


def _restore_household_users(
    db: Session,
    *,
    bundle: dict[str, Any],
    role_id_map: dict[UUID, UUID],
) -> tuple[dict[UUID, UUID], dict[str, int]]:
    user_id_map: dict[UUID, UUID] = {}
    created_user_count = 0
    reused_user_count = 0
    platform_role_stripped_count = 0

    for row in _deserialize_table_rows(bundle, table_name="users"):
        original_id = row.get("id")
        raw_email = row.get("email")
        if not isinstance(original_id, UUID) or not isinstance(raw_email, str):
            continue

        normalized_email = normalize_email(raw_email)
        existing_user = db.scalar(select(User).where(User.email == normalized_email))
        if existing_user is not None:
            user_id_map[original_id] = existing_user.id
            reused_user_count += 1
            continue

        platform_role_id = row.get("platform_role_id")
        if isinstance(platform_role_id, UUID) and platform_role_id in role_id_map:
            platform_role_stripped_count += 1

        user = User(
            email=normalized_email,
            password_hash=str(row.get("password_hash") or ""),
            display_name=row.get("display_name") if isinstance(row.get("display_name"), str) else None,
            is_active=bool(row.get("is_active", True)),
            platform_role_id=None,
            last_login_at=row.get("last_login_at"),
            dietary_preferences=row.get("dietary_preferences"),
        )
        if not user.password_hash:
            raise ValueError(f"Backup user {normalized_email} is missing a password hash.")

        db.add(user)
        db.flush()
        user_id_map[original_id] = user.id
        created_user_count += 1

    return user_id_map, {
        "created_user_count": created_user_count,
        "reused_user_count": reused_user_count,
        "platform_role_stripped_count": platform_role_stripped_count,
    }


def _restore_household_memberships(
    db: Session,
    *,
    bundle: dict[str, Any],
    target_household: Household,
    user_id_map: dict[UUID, UUID],
    role_id_map: dict[UUID, UUID],
) -> int:
    created_count = 0
    for row in _deserialize_table_rows(bundle, table_name="memberships"):
        user_id = user_id_map.get(row.get("user_id"))
        role_id = role_id_map.get(row.get("role_id"))
        if user_id is None or role_id is None:
            continue

        membership = Membership(
            user_id=user_id,
            household_id=target_household.id,
            role_id=role_id,
            is_active=bool(row.get("is_active", True)),
        )
        db.add(membership)
        created_count += 1

    db.flush()
    return created_count


def _restore_household_tables(
    db: Session,
    *,
    bundle: dict[str, Any],
    target_household: Household,
    user_id_map: dict[UUID, UUID],
) -> dict[str, int]:
    table_counts: dict[str, int] = {}
    id_maps: dict[str, dict[UUID, UUID]] = {
        "location_groups": {},
        "locations": {},
        "products": {},
        "product_aliases": {},
        "barcodes": {},
        "stock_lots": {},
        "shopping_lists": {},
        "shopping_list_items": {},
        "recipes": {},
        "recipe_ingredients": {},
        "recipe_url_imports": {},
        "import_jobs": {},
        "import_source_files": {},
        "import_lines": {},
        "product_enrichments": {},
        "ai_provider_configs": {},
    }

    for row in _deserialize_table_rows(bundle, table_name="location_groups"):
        original_id = row["id"]
        copied = _copy_row_for_household_restore(row, table_name="location_groups", household_id=target_household.id)
        id_maps["location_groups"][original_id] = copied["id"]
        db.execute(Base.metadata.tables["location_groups"].insert(), [copied])
    table_counts["location_groups"] = len(id_maps["location_groups"])

    for row in _deserialize_table_rows(bundle, table_name="locations"):
        original_id = row["id"]
        copied = _copy_row_for_household_restore(row, table_name="locations", household_id=target_household.id)
        copied["location_group_id"] = id_maps["location_groups"][row["location_group_id"]]
        id_maps["locations"][original_id] = copied["id"]
        db.execute(Base.metadata.tables["locations"].insert(), [copied])
    table_counts["locations"] = len(id_maps["locations"])

    for row in _deserialize_table_rows(bundle, table_name="products"):
        original_id = row["id"]
        copied = _copy_row_for_household_restore(row, table_name="products", household_id=target_household.id)
        id_maps["products"][original_id] = copied["id"]
        db.execute(Base.metadata.tables["products"].insert(), [copied])
    table_counts["products"] = len(id_maps["products"])

    for row in _deserialize_table_rows(bundle, table_name="product_aliases"):
        original_id = row["id"]
        copied = _copy_row_for_household_restore(row, table_name="product_aliases", household_id=target_household.id)
        copied["product_id"] = id_maps["products"][row["product_id"]]
        id_maps["product_aliases"][original_id] = copied["id"]
        db.execute(Base.metadata.tables["product_aliases"].insert(), [copied])
    table_counts["product_aliases"] = len(id_maps["product_aliases"])

    for row in _deserialize_table_rows(bundle, table_name="barcodes"):
        original_id = row["id"]
        copied = _copy_row_for_household_restore(row, table_name="barcodes", household_id=target_household.id)
        copied["product_id"] = id_maps["products"][row["product_id"]]
        id_maps["barcodes"][original_id] = copied["id"]
        db.execute(Base.metadata.tables["barcodes"].insert(), [copied])
    table_counts["barcodes"] = len(id_maps["barcodes"])

    for row in _deserialize_table_rows(bundle, table_name="stock_lots"):
        original_id = row["id"]
        copied = _copy_row_for_household_restore(row, table_name="stock_lots", household_id=target_household.id)
        copied["product_id"] = id_maps["products"][row["product_id"]]
        copied["location_id"] = id_maps["locations"][row["location_id"]]
        id_maps["stock_lots"][original_id] = copied["id"]
        db.execute(Base.metadata.tables["stock_lots"].insert(), [copied])
    table_counts["stock_lots"] = len(id_maps["stock_lots"])

    for row in _deserialize_table_rows(bundle, table_name="shopping_lists"):
        original_id = row["id"]
        copied = _copy_row_for_household_restore(row, table_name="shopping_lists", household_id=target_household.id)
        id_maps["shopping_lists"][original_id] = copied["id"]
        db.execute(
            Base.metadata.tables["shopping_lists"].insert(),
            [{**copied, "merged_into_list_id": None}],
        )
    for row in _deserialize_table_rows(bundle, table_name="shopping_lists"):
        merged_into_list_id = row.get("merged_into_list_id")
        if not isinstance(merged_into_list_id, UUID):
            continue
        db.execute(
            Base.metadata.tables["shopping_lists"].update().where(
                Base.metadata.tables["shopping_lists"].c.id == id_maps["shopping_lists"][row["id"]]
            ).values(merged_into_list_id=id_maps["shopping_lists"][merged_into_list_id])
        )
    table_counts["shopping_lists"] = len(id_maps["shopping_lists"])

    for row in _deserialize_table_rows(bundle, table_name="shopping_list_items"):
        original_id = row["id"]
        copied = _copy_row_for_household_restore(
            row,
            table_name="shopping_list_items",
            household_id=target_household.id,
        )
        copied["shopping_list_id"] = id_maps["shopping_lists"][row["shopping_list_id"]]
        product_id = row.get("product_id")
        copied["product_id"] = id_maps["products"].get(product_id) if isinstance(product_id, UUID) else None
        id_maps["shopping_list_items"][original_id] = copied["id"]
        db.execute(Base.metadata.tables["shopping_list_items"].insert(), [copied])
    table_counts["shopping_list_items"] = len(id_maps["shopping_list_items"])

    for row in _deserialize_table_rows(bundle, table_name="recipes"):
        original_id = row["id"]
        copied = _copy_row_for_household_restore(row, table_name="recipes", household_id=target_household.id)
        id_maps["recipes"][original_id] = copied["id"]
        db.execute(Base.metadata.tables["recipes"].insert(), [copied])
    table_counts["recipes"] = len(id_maps["recipes"])

    for row in _deserialize_table_rows(bundle, table_name="recipe_ingredients"):
        original_id = row["id"]
        copied = _copy_row_for_household_restore(
            row,
            table_name="recipe_ingredients",
            household_id=target_household.id,
        )
        copied["recipe_id"] = id_maps["recipes"][row["recipe_id"]]
        product_id = row.get("product_id")
        copied["product_id"] = id_maps["products"].get(product_id) if isinstance(product_id, UUID) else None
        id_maps["recipe_ingredients"][original_id] = copied["id"]
        db.execute(Base.metadata.tables["recipe_ingredients"].insert(), [copied])
    table_counts["recipe_ingredients"] = len(id_maps["recipe_ingredients"])

    for row in _deserialize_table_rows(bundle, table_name="recipe_url_imports"):
        original_id = row["id"]
        copied = _copy_row_for_household_restore(
            row,
            table_name="recipe_url_imports",
            household_id=target_household.id,
        )
        recipe_id = row.get("recipe_id")
        copied["recipe_id"] = id_maps["recipes"].get(recipe_id) if isinstance(recipe_id, UUID) else None
        requested_by_user_id = row.get("requested_by_user_id")
        copied["requested_by_user_id"] = (
            user_id_map.get(requested_by_user_id) if isinstance(requested_by_user_id, UUID) else None
        )
        id_maps["recipe_url_imports"][original_id] = copied["id"]
        db.execute(Base.metadata.tables["recipe_url_imports"].insert(), [copied])
    table_counts["recipe_url_imports"] = len(id_maps["recipe_url_imports"])

    for row in _deserialize_table_rows(bundle, table_name="import_jobs"):
        original_id = row["id"]
        copied = _copy_row_for_household_restore(row, table_name="import_jobs", household_id=target_household.id)
        requested_by_user_id = row.get("requested_by_user_id")
        copied["requested_by_user_id"] = (
            user_id_map.get(requested_by_user_id) if isinstance(requested_by_user_id, UUID) else None
        )
        id_maps["import_jobs"][original_id] = copied["id"]
        db.execute(Base.metadata.tables["import_jobs"].insert(), [copied])
    table_counts["import_jobs"] = len(id_maps["import_jobs"])

    for row in _deserialize_table_rows(bundle, table_name="import_lines"):
        original_id = row["id"]
        copied = _copy_row_for_household_restore(row, table_name="import_lines", household_id=target_household.id)
        copied["import_job_id"] = id_maps["import_jobs"][row["import_job_id"]]
        product_id = row.get("product_id")
        suggested_product_id = row.get("suggested_product_id")
        confirmed_stock_lot_id = row.get("confirmed_stock_lot_id")
        copied["product_id"] = id_maps["products"].get(product_id) if isinstance(product_id, UUID) else None
        copied["suggested_product_id"] = (
            id_maps["products"].get(suggested_product_id) if isinstance(suggested_product_id, UUID) else None
        )
        copied["confirmed_stock_lot_id"] = (
            id_maps["stock_lots"].get(confirmed_stock_lot_id)
            if isinstance(confirmed_stock_lot_id, UUID)
            else None
        )
        id_maps["import_lines"][original_id] = copied["id"]
        db.execute(Base.metadata.tables["import_lines"].insert(), [copied])
    table_counts["import_lines"] = len(id_maps["import_lines"])

    for row in _deserialize_table_rows(bundle, table_name="product_enrichments"):
        original_id = row["id"]
        copied = _copy_row_for_household_restore(
            row,
            table_name="product_enrichments",
            household_id=target_household.id,
        )
        copied["product_id"] = id_maps["products"][row["product_id"]]
        id_maps["product_enrichments"][original_id] = copied["id"]
        db.execute(Base.metadata.tables["product_enrichments"].insert(), [copied])
    table_counts["product_enrichments"] = len(id_maps["product_enrichments"])

    for row in _deserialize_table_rows(bundle, table_name="ai_provider_configs"):
        original_id = row["id"]
        copied = _copy_row_for_household_restore(
            row,
            table_name="ai_provider_configs",
            household_id=target_household.id,
        )
        if copied.get("scope_type") == "household":
            copied["scope_key"] = target_household.external_id
        id_maps["ai_provider_configs"][original_id] = copied["id"]
        db.execute(Base.metadata.tables["ai_provider_configs"].insert(), [copied])
    table_counts["ai_provider_configs"] = len(id_maps["ai_provider_configs"])

    return table_counts


def restore_household_backup_bundle(
    db: Session,
    *,
    bundle: dict[str, Any],
    actor: User,
    target_household_name: str,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    compatibility, bundle_household = _validate_household_restore_bundle(db, bundle)

    normalized_name = target_household_name.strip()
    if not normalized_name:
        raise ValueError("A restore target household name is required.")

    existing_household = db.scalar(
        select(Household).where(func.lower(Household.name) == normalized_name.casefold())
    )
    if existing_household is not None:
        raise ValueError(
            "A household with that restore target name already exists. Rename the restore target or delete the existing household first."
        )

    try:
        target_household = Household(
            name=normalized_name,
            dietary_preferences=bundle_household.get("dietary_preferences"),
        )
        db.add(target_household)
        db.flush()

        role_id_map = _build_role_id_map(db, bundle=bundle)
        user_id_map, user_counts = _restore_household_users(db, bundle=bundle, role_id_map=role_id_map)
        membership_count = _restore_household_memberships(
            db,
            bundle=bundle,
            target_household=target_household,
            user_id_map=user_id_map,
            role_id_map=role_id_map,
        )
        restored_table_counts = _restore_household_tables(
            db,
            bundle=bundle,
            target_household=target_household,
            user_id_map=user_id_map,
        )

        warnings = list(compatibility.warnings)
        warnings.append(
            "Household restore always creates a new household. Pantry does not merge or overwrite an existing household through this flow."
        )
        warnings.append(
            "Historical household audit events are not replayed during household restore. Pantry records a new restore audit event instead."
        )
        warnings.append(
            "Uploaded import source files are not replayed during household restore. Import history is restored without original upload blobs."
        )
        if user_counts["platform_role_stripped_count"] > 0:
            warnings.append(
                "Platform admin privileges from household backup users are not restored through the household restore flow."
            )
        if compatibility.allowed_missing_tables:
            warnings.append(
                "This backup came from an older Pantry schema. Pantry restored the compatible data it could, but some records may be missing."
            )

        record_audit_event(
            db,
            household=target_household,
            actor=actor,
            action="admin.household.restored",
            target_type="household",
            target_external_id=target_household.external_id,
            event_metadata={
                "target_name": target_household.name,
                "source_household_external_id": bundle.get("metadata", {}).get("household_external_id"),
                "source_household_name": bundle.get("metadata", {}).get("household_name"),
                "bundle_schema_revision": bundle.get("schema_revision"),
                "created_user_count": user_counts["created_user_count"],
                "reused_user_count": user_counts["reused_user_count"],
                "membership_count": membership_count,
                "restored_tables": restored_table_counts,
                "warnings": warnings,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    restored_bundle_summary = _bundle_summary(bundle)
    restored_bundle_summary["household_external_id"] = target_household.external_id
    restored_bundle_summary["household_name"] = target_household.name
    return restored_bundle_summary, tuple(warnings)


def backup_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bundle_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    return _bundle_summary(bundle)
