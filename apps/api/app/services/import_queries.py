from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.import_job import ImportJob
from app.models.import_line import ImportLine
from app.schemas.imports import (
    ImportCountsSummary,
    ImportDetail,
    ImportDetailResponse,
    ImportJobSummary,
    ImportLineSummary,
    ImportLinkedProductSummary,
    ImportListResponse,
    ImportSourceFileSummary,
)
from app.services.import_workflow import get_import_job_by_external_id
from app.services.tenancy import HouseholdAccess


def _build_counts(import_job: ImportJob) -> ImportCountsSummary:
    return ImportCountsSummary(
        line_count=import_job.line_count,
        matched_line_count=import_job.matched_line_count,
        needs_review_line_count=import_job.needs_review_line_count,
        unresolved_line_count=import_job.unresolved_line_count,
        ignored_line_count=import_job.ignored_line_count,
        confirmed_line_count=import_job.confirmed_line_count,
    )


def _build_product_summary(product) -> ImportLinkedProductSummary | None:
    if product is None:
        return None
    return ImportLinkedProductSummary(
        external_id=product.external_id,
        name=product.name,
        default_unit=product.default_unit,
    )


def _build_source_files(import_job: ImportJob) -> list[ImportSourceFileSummary]:
    return [
        ImportSourceFileSummary.model_validate(source_file)
        for source_file in sorted(import_job.source_files, key=lambda item: item.created_at)
    ]


def _build_requested_by_display(import_job: ImportJob) -> str | None:
    if import_job.requested_by_user is None:
        return None
    return import_job.requested_by_user.display_name or import_job.requested_by_user.email


def _build_import_job_summary(import_job: ImportJob) -> ImportJobSummary:
    return ImportJobSummary(
        external_id=import_job.external_id,
        source_type=import_job.source_type,
        status=import_job.status,
        source_label=import_job.source_label,
        note=import_job.note,
        occurred_on=import_job.occurred_on,
        parser_kind=import_job.parser_kind,
        failure_message=import_job.failure_message,
        requested_by_display=_build_requested_by_display(import_job),
        counts=_build_counts(import_job),
        source_files=_build_source_files(import_job),
        created_at=import_job.created_at,
        updated_at=import_job.updated_at,
        processed_at=import_job.processed_at,
        confirmed_at=import_job.confirmed_at,
    )


def _build_import_line_summary(line: ImportLine) -> ImportLineSummary:
    return ImportLineSummary(
        external_id=line.external_id,
        position=line.position,
        source_reference=line.source_reference,
        raw_label=line.raw_label,
        quantity=line.quantity,
        unit=line.unit,
        barcode=line.barcode,
        note=line.note,
        purchased_on=line.purchased_on,
        expires_on=line.expires_on,
        status=line.status,
        match_basis=line.match_basis,
        product=_build_product_summary(line.product),
        suggested_product=_build_product_summary(line.suggested_product),
        confirmed_stock_lot_external_id=(
            line.confirmed_stock_lot.external_id if line.confirmed_stock_lot is not None else None
        ),
        updated_at=line.updated_at,
    )


def build_import_list_response(
    db: Session,
    *,
    access: HouseholdAccess,
) -> ImportListResponse:
    import_jobs = db.scalars(
        select(ImportJob)
        .where(ImportJob.household_id == access.household.id)
        .options(selectinload(ImportJob.requested_by_user), selectinload(ImportJob.source_files))
        .order_by(ImportJob.created_at.desc())
    ).all()

    return ImportListResponse(
        household_external_id=access.household.external_id,
        household_name=access.household.name,
        effective_role=access.effective_role,
        can_administer=access.can_administer,
        imports=[_build_import_job_summary(import_job) for import_job in import_jobs],
    )


def build_import_detail_response(
    db: Session,
    *,
    access: HouseholdAccess,
    import_external_id: str,
) -> ImportDetailResponse:
    import_job = get_import_job_by_external_id(
        db,
        household=access.household,
        import_external_id=import_external_id,
    )
    if import_job is None:
        raise ValueError("Import job not found.")

    lines = sorted(import_job.lines, key=lambda item: item.position)
    blocking_line_count = sum(1 for line in lines if line.status not in {"matched", "ignored", "confirmed"})
    ready_to_confirm = bool(lines) and blocking_line_count == 0 and import_job.status not in {
        "confirmed",
        "failed",
        "queued",
        "processing",
    }

    return ImportDetailResponse(
        household_external_id=access.household.external_id,
        household_name=access.household.name,
        effective_role=access.effective_role,
        can_administer=access.can_administer,
        import_job=ImportDetail(
            external_id=import_job.external_id,
            source_type=import_job.source_type,
            status=import_job.status,
            source_label=import_job.source_label,
            note=import_job.note,
            occurred_on=import_job.occurred_on,
            parser_kind=import_job.parser_kind,
            failure_message=import_job.failure_message,
            requested_by_display=_build_requested_by_display(import_job),
            counts=_build_counts(import_job),
            source_files=_build_source_files(import_job),
            lines=[_build_import_line_summary(line) for line in lines],
            ready_to_confirm=ready_to_confirm,
            blocking_line_count=blocking_line_count,
            created_at=import_job.created_at,
            updated_at=import_job.updated_at,
            processed_at=import_job.processed_at,
            confirmed_at=import_job.confirmed_at,
        ),
    )
