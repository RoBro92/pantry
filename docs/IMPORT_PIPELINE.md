# Import Pipeline

Imports are a major future capability and a major security boundary.

## Design Principles

- Uploaded files are hostile input.
- Parsing, extraction, and normalization should run in controlled worker paths.
- Source files, extracted lines, and normalized domain decisions should be separate records.
- Human review should remain possible for ambiguous imports.
- Pantry stock must never change before explicit confirmation of reviewed lines.

## Current Foundation

Milestone 4 now implements the reviewed import foundation for household pantry ingestion.

- API upload endpoints store files outside any web-served path under a configurable import-storage root.
- Application-level validation currently enforces file size limits and a restricted type set for text, CSV, TSV, JSON, PDF, PNG, and JPEG uploads.
- Worker processing currently supports deterministic/manual-friendly parsers for JSON, CSV, TSV, and plain-text line imports.
- PDF and image uploads are accepted into the safe storage path and tracked in history, but parsing/OCR is intentionally deferred.
- Each import creates an `ImportJob`, one or more `ImportSourceFile` records, and reviewable `ImportLine` rows.
- Deterministic matching currently uses barcode exact match first, then canonical product name, then product alias.
- Review flows allow line edits, manual product selection, ignore actions, and explicit confirm-to-pantry writes.
- Confirmed lines create `StockLot` records rather than flattening totals, and safe alias learning can add new `ProductAlias` records from confirmed matches.

## Current Flow

1. Client uploads a source file and chooses an import source type.
2. API validates size/type, stores the file in non-web storage, creates an `ImportJob`, and records audit activity.
3. Worker picks up queued jobs, parses supported structured/text inputs, and extracts `ImportLine` records.
4. Worker applies deterministic product suggestions and moves the job to `needs_review` or `failed`.
5. User reviews, edits, matches, or ignores lines.
6. User explicitly confirms the reviewed import into a chosen pantry location.
7. API creates `StockLot` records for matched lines only and marks the import confirmed.

## Guardrails

- Never trust MIME type or filename alone.
- Do not execute embedded content.
- Keep raw uploads, parsed results, and final domain writes distinct.
- Avoid mixing import-specific heuristics directly into core pantry domain services.
- Record validation and scan status even before a full malware-scanning or quarantine subsystem exists.

## Deferred Work

- Malware scanning and quarantine enforcement beyond the current validation/status foundation.
- PDF/image OCR and receipt extraction beyond safe storage and visible failure states.
- Retailer-specific online-order parsers and supermarket integrations.
- AI-assisted parsing, matching, and review suggestions.
- Full recipe URL parsing execution through the shared import-job architecture.
