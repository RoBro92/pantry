# Import Pipeline

Imports are a major future capability and a major security boundary.

## Design Principles

- Uploaded files are hostile input.
- Parsing, extraction, and normalization should run in controlled worker paths.
- Source files, extracted lines, and normalized domain decisions should be separate records.
- Human review should remain possible for ambiguous imports.

## Planned Flow

1. Client uploads a source file.
2. API stores metadata and creates an `ImportJob`.
3. Worker validates and scans the file in a restricted processing path.
4. Worker extracts candidate lines or records into `ImportLine`.
5. User reviews, accepts, edits, or rejects results before domain writes occur.

## Guardrails

- Never trust MIME type or filename alone.
- Do not execute embedded content.
- Keep raw uploads, parsed results, and final domain writes distinct.
- Avoid mixing import-specific heuristics directly into core pantry domain services.

