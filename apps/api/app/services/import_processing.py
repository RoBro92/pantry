from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import and_, case, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models.base import utc_now
from app.models.import_job import ImportJob
from app.models.import_line import ImportLine
from app.services.audit import record_audit_event
from app.services.import_matching import resolve_import_line_match
from app.services.import_storage import resolve_storage_path
from app.services.import_workflow import fail_import_job, refresh_import_job_counts
from app.services.pantry_normalization import normalize_barcode, normalize_lookup_name, normalize_unit, require_text

logger = structlog.get_logger(__name__)
IMPORT_JOB_RESUME_TIMEOUT = timedelta(minutes=15)


@dataclass(frozen=True)
class ParsedImportLine:
    source_reference: str | None
    raw_label: str
    quantity: Decimal
    unit: str
    barcode: str | None
    note: str | None
    purchased_on: date | None = None
    expires_on: date | None = None
    force_status: str | None = None


def _normalize_quantity(value: object | None) -> tuple[Decimal, str | None, str | None]:
    if value in (None, ""):
        return Decimal("1.000"), None, None
    try:
        quantity = Decimal(str(value))
    except Exception:
        return Decimal("1.000"), "Quantity was invalid and defaulted to 1.000 for review.", "needs_review"
    if quantity <= Decimal("0"):
        return Decimal("1.000"), "Quantity must be greater than zero and was defaulted to 1.000 for review.", "needs_review"
    return quantity.quantize(Decimal("0.001")), None, None


def _parse_optional_date(value: object | None, *, field_name: str) -> tuple[date | None, str | None, str | None]:
    if value in (None, ""):
        return None, None, None
    try:
        return date.fromisoformat(str(value)), None, None
    except ValueError:
        return None, f"{field_name} was invalid and was cleared for review.", "needs_review"


def _merge_notes(*parts: str | None) -> str | None:
    values = [part.strip() for part in parts if part and part.strip()]
    return " ".join(values) if values else None


def _merge_statuses(*statuses: str | None) -> str | None:
    if "needs_review" in statuses:
        return "needs_review"
    return None


def _is_empty_record(record: dict[str, object]) -> bool:
    return not any(str(value).strip() for value in record.values() if value not in (None, ""))


def _coerce_parsed_line(record: dict[str, object], *, source_reference: str | None) -> ParsedImportLine | None:
    if _is_empty_record(record):
        return None

    raw_label_value = str(record.get("name") or record.get("label") or record.get("item") or "")
    raw_label = raw_label_value.strip() or (source_reference or "Imported line")
    note = require_text(str(record["note"]), field_name="Line note") if record.get("note") else None
    quantity, quantity_note, quantity_status = _normalize_quantity(record.get("quantity") or record.get("qty"))
    purchased_on, purchased_note, purchased_status = _parse_optional_date(
        record.get("purchased_on"),
        field_name="Purchased date",
    )
    expires_on, expires_note, expires_status = _parse_optional_date(
        record.get("expires_on"),
        field_name="Expiry date",
    )
    force_status = _merge_statuses(
        "needs_review" if not raw_label_value.strip() else None,
        quantity_status,
        purchased_status,
        expires_status,
    )
    if purchased_on and expires_on and expires_on < purchased_on:
        purchased_on = None
        expires_on = None
        force_status = _merge_statuses(force_status, "needs_review")
        note = _merge_notes(note, "Purchase and expiry dates were inconsistent and were cleared for review.")
    note = _merge_notes(
        note,
        "Line label was missing and needs review." if not raw_label_value.strip() else None,
        quantity_note,
        purchased_note,
        expires_note,
    )
    barcode = record.get("barcode")
    return ParsedImportLine(
        source_reference=source_reference,
        raw_label=require_text(raw_label, field_name="Line label"),
        quantity=quantity,
        unit=normalize_unit(str(record.get("unit") or "count")),
        barcode=normalize_barcode(str(barcode)) if barcode not in (None, "") else None,
        note=note,
        purchased_on=purchased_on,
        expires_on=expires_on,
        force_status=force_status,
    )


def _parse_json_lines(payload: bytes) -> tuple[list[ParsedImportLine], str, date | None]:
    data = json.loads(payload.decode("utf-8"))
    parser_kind = "json_structured"
    occurred_on = None

    if isinstance(data, dict):
        if data.get("occurred_on"):
            occurred_on = date.fromisoformat(str(data["occurred_on"]))
        line_data = data.get("lines", [])
    elif isinstance(data, list):
        line_data = data
    else:
        raise ValueError("JSON import must be an object with lines or a list of lines.")

    parsed_lines: list[ParsedImportLine] = []
    for index, item in enumerate(line_data, start=1):
        if isinstance(item, str):
            parsed_lines.append(
                ParsedImportLine(
                    source_reference=f"line:{index}",
                    raw_label=require_text(item, field_name="Line label"),
                    quantity=Decimal("1.000"),
                    unit="count",
                    barcode=None,
                    note=None,
                )
            )
            continue

        if not isinstance(item, dict):
            raise ValueError("Each JSON import line must be a string or object.")
        parsed_line = _coerce_parsed_line(item, source_reference=f"line:{index}")
        if parsed_line is not None:
            parsed_lines.append(parsed_line)

    return parsed_lines, parser_kind, occurred_on


def _first_matching_value(row: dict[str, str], names: list[str]) -> str | None:
    lowered = {key.strip().lower(): value for key, value in row.items() if key is not None}
    for name in names:
        if name in lowered:
            value = lowered[name]
            return value if value != "" else None
    return None


def _parse_delimited_lines(text: str, *, delimiter: str) -> tuple[list[ParsedImportLine], str]:
    parser_kind = "tsv" if delimiter == "\t" else "csv"
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("Delimited imports must include a header row.")

    parsed_lines: list[ParsedImportLine] = []
    for index, row in enumerate(reader, start=2):
        parsed_line = _coerce_parsed_line(
            {
                "name": _first_matching_value(row, ["name", "label", "item", "product"]),
                "quantity": _first_matching_value(row, ["quantity", "qty"]),
                "unit": _first_matching_value(row, ["unit"]),
                "barcode": _first_matching_value(row, ["barcode", "ean", "upc"]),
                "note": _first_matching_value(row, ["note", "notes"]),
                "purchased_on": _first_matching_value(row, ["purchased_on"]),
                "expires_on": _first_matching_value(row, ["expires_on"]),
            },
            source_reference=f"row:{index}",
        )
        if parsed_line is not None:
            parsed_lines.append(parsed_line)

    return parsed_lines, parser_kind


def _parse_plain_text_lines(text: str) -> tuple[list[ParsedImportLine], str]:
    parsed_lines = [
        ParsedImportLine(
            source_reference=f"line:{index}",
            raw_label=require_text(line, field_name="Line label"),
            quantity=Decimal("1.000"),
            unit="count",
            barcode=None,
            note=None,
        )
        for index, line in enumerate(text.splitlines(), start=1)
        if line.strip()
    ]
    return parsed_lines, "plain_text_lines"


def _extract_parsed_lines(import_job: ImportJob) -> tuple[list[ParsedImportLine], str, date | None]:
    source_file = import_job.source_files[0] if import_job.source_files else None
    if source_file is None:
        raise ValueError("Import job has no source file.")

    storage_path = resolve_storage_path(get_settings(), source_file.storage_path)
    payload = storage_path.read_bytes()
    detected_type = source_file.detected_content_type or ""

    if detected_type == "application/json":
        return _parse_json_lines(payload)
    if detected_type == "text/csv":
        lines, parser_kind = _parse_delimited_lines(payload.decode("utf-8"), delimiter=",")
        return lines, parser_kind, None
    if detected_type == "text/tab-separated-values":
        lines, parser_kind = _parse_delimited_lines(payload.decode("utf-8"), delimiter="\t")
        return lines, parser_kind, None
    if detected_type == "text/plain":
        lines, parser_kind = _parse_plain_text_lines(payload.decode("utf-8"))
        return lines, parser_kind, None
    if detected_type in {"application/pdf", "image/png", "image/jpeg"}:
        raise ValueError("Parsing for PDF and image imports is not implemented yet.")

    raise ValueError("No parser is available for this import type.")


def _claim_next_import_job(db: Session) -> ImportJob | None:
    resume_before = utc_now() - IMPORT_JOB_RESUME_TIMEOUT
    import_job = db.scalar(
        select(ImportJob)
        .where(
            or_(
                ImportJob.status == "queued",
                and_(
                    ImportJob.status == "processing",
                    or_(
                        ImportJob.processing_started_at.is_(None),
                        ImportJob.processing_started_at < resume_before,
                    ),
                ),
            )
        )
        .options(
            selectinload(ImportJob.household),
            selectinload(ImportJob.source_files),
            selectinload(ImportJob.lines),
        )
        .order_by(case((ImportJob.status == "queued", 0), else_=1), ImportJob.created_at.asc())
        .with_for_update(skip_locked=True)
    )
    if import_job is None:
        return None

    import_job.status = "processing"
    import_job.processing_started_at = utc_now()
    import_job.failure_message = None
    db.add(import_job)
    db.commit()
    return db.scalar(
        select(ImportJob)
        .where(ImportJob.id == import_job.id)
        .options(
            selectinload(ImportJob.household),
            selectinload(ImportJob.source_files),
            selectinload(ImportJob.lines),
        )
    )


def process_next_import_job() -> bool:
    with SessionLocal() as db:
        import_job = _claim_next_import_job(db)
        if import_job is None:
            return False

        structlog.contextvars.bind_contextvars(
            import_job_external_id=import_job.external_id,
            household_external_id=import_job.household.external_id,
        )
        logger.info("worker.import_job.claimed", source_type=import_job.source_type)

        try:
            parsed_lines, parser_kind, occurred_on = _extract_parsed_lines(import_job)
            if not parsed_lines:
                raise ValueError("No import lines could be extracted from the source.")

            for existing_line in list(import_job.lines):
                db.delete(existing_line)
            db.flush()
            import_job.lines = []

            if import_job.occurred_on is None and occurred_on is not None:
                import_job.occurred_on = occurred_on

            for index, parsed_line in enumerate(parsed_lines, start=1):
                match_result = resolve_import_line_match(
                    db,
                    household=import_job.household,
                    raw_label=parsed_line.raw_label,
                    barcode=parsed_line.barcode,
                )
                line = ImportLine(
                    household_id=import_job.household_id,
                    import_job_id=import_job.id,
                    product_id=match_result.product.id if match_result.product is not None else None,
                    suggested_product_id=match_result.product.id if match_result.product is not None else None,
                    position=index,
                    source_reference=parsed_line.source_reference,
                    raw_label=parsed_line.raw_label,
                    normalized_label=normalize_lookup_name(parsed_line.raw_label),
                    quantity=parsed_line.quantity,
                    unit=parsed_line.unit,
                    barcode=parsed_line.barcode,
                    note=parsed_line.note,
                    purchased_on=parsed_line.purchased_on,
                    expires_on=parsed_line.expires_on,
                    status=parsed_line.force_status or match_result.status,
                    match_basis=match_result.match_basis,
                )
                if parsed_line.force_status == "needs_review":
                    line.status = "needs_review"
                import_job.lines.append(line)
                db.add(line)

            import_job.parser_kind = parser_kind
            import_job.status = "needs_review"
            import_job.processed_at = utc_now()
            import_job.failure_message = None
            refresh_import_job_counts(import_job)
            record_audit_event(
                db,
                household=import_job.household,
                actor=None,
                action="import.review_ready",
                target_type="import_job",
                target_external_id=import_job.external_id,
                event_metadata={
                    "parser_kind": parser_kind,
                    "line_count": import_job.line_count,
                    "matched_line_count": import_job.matched_line_count,
                    "unresolved_line_count": import_job.unresolved_line_count,
                },
            )
            db.add(import_job)
            db.commit()
            logger.info(
                "worker.import_job.completed",
                parser_kind=parser_kind,
                line_count=import_job.line_count,
                matched_line_count=import_job.matched_line_count,
                unresolved_line_count=import_job.unresolved_line_count,
            )
        except Exception as exc:
            db.rollback()
            import_job = db.scalar(
                select(ImportJob)
                .where(ImportJob.id == import_job.id)
                .options(selectinload(ImportJob.household), selectinload(ImportJob.source_files))
            )
            if import_job is None:
                raise
            fail_import_job(db, import_job=import_job, message=str(exc))
            logger.exception("worker.import_job.failed", error=str(exc))
        finally:
            structlog.contextvars.unbind_contextvars("import_job_external_id", "household_external_id")

    return True
