from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Date, DateTime, Numeric, Uuid, delete, select, text
from sqlalchemy.orm import Session

from app.core.config import AppSettings, get_settings
from app.models.base import Base
from app.models.household import Household
from app.models.membership import Membership
from app.models.user import User
from app.services.audit import record_audit_event
from app.services.import_storage import sanitize_upload_filename

if TYPE_CHECKING:
    from fastapi import UploadFile

BACKUP_FORMAT = "pantry.backup.bundle"
BACKUP_FORMAT_VERSION = 1
ALLOWED_BACKUP_EXTENSIONS = {".json"}
RESTORE_CONFIRMATION_PHRASE = "RESTORE PANTRY INSTANCE"
HOUSEHOLD_EXPORT_TABLES = {
    "roles",
    "users",
    "households",
    "memberships",
    "location_groups",
    "locations",
    "products",
    "product_aliases",
    "barcodes",
    "stock_lots",
    "recipes",
    "recipe_ingredients",
    "recipe_url_imports",
    "import_jobs",
    "import_source_files",
    "import_lines",
    "ai_provider_configs",
    "audit_events",
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


def _validate_restore_bundle(db: Session, bundle: dict[str, Any]) -> None:
    payload = _validate_bundle_payload(bundle)
    if payload["scope"] != "instance":
        raise ValueError("Only full instance Pantry backups can be restored in this milestone.")

    current_revision = _current_schema_revision(db)
    bundle_revision = payload.get("schema_revision")
    if current_revision != bundle_revision:
        raise ValueError(
            "Backup schema revision does not match the running Pantry schema. Export and restore must currently use the same migrated schema revision."
        )

    expected_tables = {table.name for table in Base.metadata.sorted_tables}
    actual_tables = set((payload.get("tables") or {}).keys())
    if expected_tables != actual_tables:
        missing_tables = sorted(expected_tables - actual_tables)
        unexpected_tables = sorted(actual_tables - expected_tables)
        details: list[str] = []
        if missing_tables:
            details.append(f"missing tables: {', '.join(missing_tables)}")
        if unexpected_tables:
            details.append(f"unexpected tables: {', '.join(unexpected_tables)}")
        suffix = f" ({'; '.join(details)})" if details else ""
        raise ValueError(f"Backup table layout does not match the running Pantry schema.{suffix}")

    roles_rows = payload["tables"].get("roles") or []
    users_rows = payload["tables"].get("users") or []
    platform_role_ids = {
        row.get("id")
        for row in roles_rows
        if row.get("code") == "platform_admin" and row.get("id")
    }
    if not any(user.get("platform_role_id") in platform_role_ids for user in users_rows):
        raise ValueError("Backup bundle must contain at least one platform admin user to restore safely.")


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
        "Restore currently supports full instance Pantry backup bundles only.",
    ]

    current_revision = _current_schema_revision(db)
    supported_for_restore = True
    if bundle["scope"] not in allowed_restore_scopes:
        supported_for_restore = False
        warnings.append("This backup scope can be exported, but it is not restorable through this flow.")
    if bundle.get("schema_revision") != current_revision:
        supported_for_restore = False
        warnings.append(
            "This backup was created from a different Pantry schema revision. Cross-version restore is not supported yet."
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
                        column.name: _deserialize_scalar(column, row.get(column.name))
                        for column in table.columns
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


def backup_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bundle_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    return _bundle_summary(bundle)
