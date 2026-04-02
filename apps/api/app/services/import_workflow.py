from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.base import utc_now
from app.models.household import Household
from app.models.import_job import ImportJob
from app.models.import_line import ImportLine
from app.models.import_source_file import ImportSourceFile
from app.models.product import Product
from app.models.stock_lot import StockLot
from app.models.user import User
from app.services.audit import record_audit_event
from app.services.import_matching import resolve_import_line_match
from app.services.import_storage import StoredImportUpload, store_import_upload
from app.services.imports_common import (
    REVIEWABLE_IMPORT_LINE_STATUSES,
    require_import_line_status,
    require_import_source_type,
)
from app.services.pantry_catalog import ensure_product_alias, get_location_by_external_id
from app.services.pantry_normalization import normalize_barcode, normalize_lookup_name, normalize_unit, require_text
from app.services.pantry_stock import add_stock_lot


def _normalize_quantity(quantity: Decimal, *, field_name: str) -> Decimal:
    if quantity <= Decimal("0"):
        raise ValueError(f"{field_name} must be greater than zero.")
    return quantity.quantize(Decimal("0.001"))


def _build_requested_by_display(user: User | None) -> str | None:
    if user is None:
        return None
    return user.display_name or user.email


def _load_import_job(
    db: Session,
    *,
    household: Household,
    import_external_id: str,
) -> ImportJob | None:
    return db.scalar(
        select(ImportJob)
        .where(ImportJob.household_id == household.id)
        .where(ImportJob.external_id == import_external_id)
        .options(
            selectinload(ImportJob.requested_by_user),
            selectinload(ImportJob.source_files),
            selectinload(ImportJob.lines).selectinload(ImportLine.product),
            selectinload(ImportJob.lines).selectinload(ImportLine.suggested_product),
            selectinload(ImportJob.lines).selectinload(ImportLine.confirmed_stock_lot),
        )
    )


def get_import_job_by_external_id(
    db: Session,
    *,
    household: Household,
    import_external_id: str,
) -> ImportJob | None:
    return _load_import_job(db, household=household, import_external_id=import_external_id)


def refresh_import_job_counts(import_job: ImportJob) -> None:
    lines = list(import_job.lines)
    import_job.line_count = len(lines)
    import_job.matched_line_count = sum(1 for line in lines if line.status == "matched")
    import_job.needs_review_line_count = sum(1 for line in lines if line.status == "needs_review")
    import_job.unresolved_line_count = sum(1 for line in lines if line.status == "unresolved")
    import_job.ignored_line_count = sum(1 for line in lines if line.status == "ignored")
    import_job.confirmed_line_count = sum(1 for line in lines if line.status == "confirmed")


async def create_import_upload(
    db: Session,
    *,
    household: Household,
    actor: User,
    source_type: str,
    occurred_on: date | None,
    note: str | None,
    upload,
) -> ImportJob:
    normalized_source_type = require_import_source_type(source_type)
    normalized_note = require_text(note, field_name="Import note") if note else None

    job = ImportJob(
        household_id=household.id,
        requested_by_user_id=actor.id,
        source_type=normalized_source_type,
        status="queued",
        source_label=require_text(upload.filename or "Upload", field_name="Upload filename"),
        note=normalized_note,
        occurred_on=occurred_on,
    )
    db.add(job)
    db.flush()

    stored_upload = await store_import_upload(
        settings=get_settings(),
        household_external_id=household.external_id,
        import_job_external_id=job.external_id,
        upload=upload,
    )
    source_file = ImportSourceFile(
        household_id=household.id,
        import_job_id=job.id,
        uploaded_by_user_id=actor.id,
        original_filename=stored_upload.original_filename,
        storage_path=stored_upload.storage_path,
        client_content_type=stored_upload.client_content_type,
        detected_content_type=stored_upload.detected_content_type,
        file_extension=stored_upload.file_extension,
        size_bytes=stored_upload.size_bytes,
        sha256_hex=stored_upload.sha256_hex,
        validation_status=stored_upload.validation_status,
        scan_status=stored_upload.scan_status,
        note=stored_upload.note,
    )
    db.add(source_file)
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="import.created",
        target_type="import_job",
        target_external_id=job.external_id,
        event_metadata={
            "source_type": job.source_type,
            "source_label": job.source_label,
            "occurred_on": occurred_on.isoformat() if occurred_on else None,
            "detected_content_type": stored_upload.detected_content_type,
            "size_bytes": stored_upload.size_bytes,
        },
    )
    db.commit()
    return get_import_job_by_external_id(db, household=household, import_external_id=job.external_id) or job


def _resolve_current_product(
    db: Session,
    *,
    household: Household,
    line: ImportLine,
    auto_match,
    updates: dict[str, object],
) -> tuple[Product | None, str]:
    if "product_external_id" in updates:
        product_external_id = updates.get("product_external_id")
        if not product_external_id:
            return auto_match.product, auto_match.match_basis
        manual_match = resolve_import_line_match(
            db,
            household=household,
            raw_label=line.raw_label,
            barcode=line.barcode,
            product_external_id=str(product_external_id),
        )
        return manual_match.product, manual_match.match_basis

    if line.match_basis == "manual" and line.product is not None:
        return line.product, line.match_basis

    return auto_match.product, auto_match.match_basis


def _validate_line_dates(*, purchased_on: date | None, expires_on: date | None) -> None:
    if purchased_on and expires_on and expires_on < purchased_on:
        raise ValueError("Expiry date cannot be earlier than purchase date.")


def update_import_line(
    db: Session,
    *,
    household: Household,
    actor: User,
    import_external_id: str,
    line_external_id: str,
    updates: dict[str, object],
) -> ImportJob:
    import_job = _load_import_job(db, household=household, import_external_id=import_external_id)
    if import_job is None:
        raise ValueError("Import job not found.")
    if import_job.status in {"queued", "processing"}:
        raise ValueError("Import job is not ready for review yet.")
    if import_job.status == "failed":
        raise ValueError("Failed imports cannot be reviewed.")
    if import_job.status == "confirmed":
        raise ValueError("Confirmed imports cannot be modified.")

    line = next((item for item in import_job.lines if item.external_id == line_external_id), None)
    if line is None:
        raise ValueError("Import line not found.")

    if "raw_label" in updates:
        line.raw_label = require_text(str(updates["raw_label"]), field_name="Import line label")
        line.normalized_label = normalize_lookup_name(line.raw_label)
    if "quantity" in updates:
        line.quantity = _normalize_quantity(Decimal(str(updates["quantity"])), field_name="Quantity")
    if "unit" in updates:
        line.unit = normalize_unit(str(updates["unit"]))
    if "barcode" in updates:
        line.barcode = normalize_barcode(str(updates["barcode"])) if updates["barcode"] else None
    if "note" in updates:
        line.note = require_text(str(updates["note"]), field_name="Import line note") if updates["note"] else None
    if "purchased_on" in updates:
        line.purchased_on = updates["purchased_on"] if isinstance(updates["purchased_on"], date) else None
    if "expires_on" in updates:
        line.expires_on = updates["expires_on"] if isinstance(updates["expires_on"], date) else None
    _validate_line_dates(purchased_on=line.purchased_on, expires_on=line.expires_on)

    auto_match = resolve_import_line_match(
        db,
        household=household,
        raw_label=line.raw_label,
        barcode=line.barcode,
    )
    current_product, current_match_basis = _resolve_current_product(
        db,
        household=household,
        line=line,
        auto_match=auto_match,
        updates=updates,
    )

    line.suggested_product_id = auto_match.product.id if auto_match.product is not None else None
    line.product_id = current_product.id if current_product is not None else None
    line.match_basis = current_match_basis if current_product is not None else "none"

    explicit_status = None
    if "status" in updates and updates["status"] is not None:
        explicit_status = require_import_line_status(str(updates["status"]))

    if explicit_status == "ignored":
        line.status = "ignored"
    elif current_product is None:
        line.status = "needs_review" if explicit_status == "needs_review" else "unresolved"
    else:
        line.status = "needs_review" if explicit_status == "needs_review" else "matched"

    import_job.status = "needs_review"
    import_job.failure_message = None
    refresh_import_job_counts(import_job)
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="import.line.reviewed",
        target_type="import_line",
        target_external_id=line.external_id,
        event_metadata={
            "import_external_id": import_job.external_id,
            "status": line.status,
            "match_basis": line.match_basis,
            "product_external_id": current_product.external_id if current_product is not None else None,
            "suggested_product_external_id": auto_match.product.external_id if auto_match.product is not None else None,
        },
    )
    db.add(import_job)
    db.commit()
    return get_import_job_by_external_id(db, household=household, import_external_id=import_job.external_id) or import_job


def _iter_pending_confirmation_lines(lines: Iterable[ImportLine]) -> list[ImportLine]:
    return [line for line in lines if line.status not in {"ignored", "confirmed"}]


def confirm_import_job(
    db: Session,
    *,
    household: Household,
    actor: User,
    import_external_id: str,
    location_external_id: str,
    purchased_on: date | None,
) -> ImportJob:
    import_job = _load_import_job(db, household=household, import_external_id=import_external_id)
    if import_job is None:
        raise ValueError("Import job not found.")
    if import_job.status in {"queued", "processing"}:
        raise ValueError("Import job is still processing.")
    if import_job.status == "failed":
        raise ValueError("Failed imports cannot be confirmed.")
    if import_job.status == "confirmed":
        raise ValueError("Import job has already been confirmed.")
    if not import_job.lines:
        raise ValueError("Import job has no lines to confirm.")

    location = get_location_by_external_id(
        db,
        household=household,
        external_id=location_external_id,
    )
    if location is None:
        raise ValueError("Location not found.")

    pending_lines = _iter_pending_confirmation_lines(import_job.lines)
    blocking_lines = [line for line in pending_lines if line.status != "matched" or line.product is None]
    if blocking_lines:
        raise ValueError("Resolve or ignore all remaining import lines before confirming.")

    alias_count = 0
    confirmed_count = 0
    for line in pending_lines:
        if line.product is None:
            continue

        lot_note_prefix = f"Imported from {import_job.source_label}"
        lot_note = line.note or None
        if lot_note_prefix and lot_note_prefix != lot_note:
            lot_note = f"{lot_note_prefix}; {lot_note}" if lot_note else lot_note_prefix

        lot = add_stock_lot(
            db,
            household=household,
            actor=actor,
            product_external_id=line.product.external_id,
            location_external_id=location.external_id,
            quantity=line.quantity,
            note=lot_note,
            purchased_on=line.purchased_on or purchased_on or import_job.occurred_on,
            expires_on=line.expires_on,
            unit_override=line.unit,
            commit=False,
        )
        line.confirmed_stock_lot_id = lot.id
        line.confirmed_stock_lot = lot
        line.status = "confirmed"
        confirmed_count += 1
        if ensure_product_alias(db, household=household, product=line.product, alias_name=line.raw_label):
            alias_count += 1

    import_job.status = "confirmed"
    import_job.confirmed_at = utc_now()
    import_job.failure_message = None
    refresh_import_job_counts(import_job)
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="import.confirmed",
        target_type="import_job",
        target_external_id=import_job.external_id,
        event_metadata={
            "location_external_id": location.external_id,
            "location_name": location.name,
            "confirmed_line_count": confirmed_count,
            "learned_alias_count": alias_count,
        },
    )
    db.add(import_job)
    db.commit()
    return get_import_job_by_external_id(db, household=household, import_external_id=import_job.external_id) or import_job


def fail_import_job(
    db: Session,
    *,
    import_job: ImportJob,
    message: str,
) -> ImportJob:
    import_job.status = "failed"
    import_job.failure_message = require_text(message, field_name="Failure message")
    import_job.processed_at = utc_now()
    record_audit_event(
        db,
        household=import_job.household,
        actor=None,
        action="import.failed",
        target_type="import_job",
        target_external_id=import_job.external_id,
        event_metadata={"failure_message": import_job.failure_message},
    )
    db.add(import_job)
    db.commit()
    return import_job
