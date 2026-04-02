from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import AppSettings

ALLOWED_UPLOAD_EXTENSIONS = {
    ".csv",
    ".jpeg",
    ".jpg",
    ".json",
    ".pdf",
    ".png",
    ".tsv",
    ".txt",
}


@dataclass(frozen=True)
class StoredImportUpload:
    original_filename: str
    storage_path: str
    client_content_type: str | None
    detected_content_type: str
    file_extension: str | None
    size_bytes: int
    sha256_hex: str
    validation_status: str
    scan_status: str
    note: str | None


def sanitize_upload_filename(filename: str | None) -> str:
    if not filename:
        return "upload.bin"
    sanitized = Path(filename).name.strip().replace("\x00", "")
    return sanitized or "upload.bin"


def resolve_storage_path(settings: AppSettings, relative_storage_path: str) -> Path:
    return Path(settings.import_storage_root).joinpath(relative_storage_path)


def _is_text_like(data: bytes) -> bool:
    if b"\x00" in data:
        return False

    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False

    return True


def _detect_content_type(
    *,
    filename: str,
    client_content_type: str | None,
    data: bytes,
) -> tuple[str, str | None]:
    extension = Path(filename).suffix.lower() or None
    if extension and extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError("Unsupported upload file type.")

    if data.startswith(b"%PDF-"):
        return "application/pdf", ".pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg" if extension not in {".jpeg", ".jpg"} else extension

    if not _is_text_like(data):
        raise ValueError("Upload content must be text, JSON, CSV, PDF, PNG, or JPEG.")

    text = data.decode("utf-8")
    if extension == ".json" or (client_content_type == "application/json" and text.strip().startswith(("{", "["))):
        json.loads(text)
        return "application/json", ".json" if extension is None else extension
    if extension == ".tsv":
        return "text/tab-separated-values", ".tsv"
    if extension == ".csv":
        return "text/csv", ".csv"
    return "text/plain", extension or ".txt"


async def store_import_upload(
    *,
    settings: AppSettings,
    household_external_id: str,
    import_job_external_id: str,
    upload: UploadFile,
) -> StoredImportUpload:
    original_filename = sanitize_upload_filename(upload.filename)
    data = await upload.read(settings.import_max_upload_bytes + 1)
    if len(data) > settings.import_max_upload_bytes:
        raise ValueError("Upload exceeds the configured size limit.")

    detected_content_type, detected_extension = _detect_content_type(
        filename=original_filename,
        client_content_type=upload.content_type,
        data=data,
    )

    storage_dir = Path(settings.import_storage_root) / household_external_id / import_job_external_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_name = f"{secrets.token_hex(16)}{detected_extension or ''}"
    storage_path = storage_dir / storage_name
    storage_path.write_bytes(data)

    note = None
    if detected_content_type in {"application/pdf", "image/png", "image/jpeg"}:
        note = "Stored safely for future scanning/OCR. Parsing is not implemented for this file type yet."

    relative_storage_path = str(storage_path.relative_to(Path(settings.import_storage_root)))

    return StoredImportUpload(
        original_filename=original_filename,
        storage_path=relative_storage_path,
        client_content_type=upload.content_type,
        detected_content_type=detected_content_type,
        file_extension=detected_extension,
        size_bytes=len(data),
        sha256_hex=hashlib.sha256(data).hexdigest(),
        validation_status="accepted",
        scan_status="not_scanned",
        note=note,
    )
