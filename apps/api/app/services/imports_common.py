from __future__ import annotations

IMPORT_SOURCE_TYPES = {
    "receipt",
    "online_order",
    "structured_import",
    "recipe_url_import",
}

IMPORT_JOB_STATUSES = {
    "queued",
    "processing",
    "needs_review",
    "confirmed",
    "failed",
}

IMPORT_LINE_STATUSES = {
    "matched",
    "needs_review",
    "unresolved",
    "ignored",
    "confirmed",
}

FINAL_IMPORT_LINE_STATUSES = {"ignored", "confirmed"}
REVIEWABLE_IMPORT_LINE_STATUSES = {"matched", "needs_review", "unresolved", "ignored"}


def require_import_source_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in IMPORT_SOURCE_TYPES:
        raise ValueError("Unsupported import source type.")
    return normalized


def require_import_line_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in IMPORT_LINE_STATUSES:
        raise ValueError("Unsupported import line status.")
    return normalized
