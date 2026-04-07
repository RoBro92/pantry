# Security

Pantry treats lifecycle and recovery inputs as hostile until proven otherwise.

## Backup Uploads

- Restore uploads currently accept Pantry backup bundle v1 JSON files only.
- Uploads are restricted by file extension, JSON parsing, schema checks, and size limits.
- The default restore upload size limit is `26214400` bytes (25 MiB) via `BACKUP_MAX_UPLOAD_BYTES`.
- Uploaded restore files are staged under `BACKUP_STORAGE_ROOT` in quarantine before use.
- Uploaded content is never executed as code.

## Restore Safety

- Restore currently supports full instance bundles only.
- Restore requires the same schema revision as the running Pantry install.
- Restore requires at least one platform admin in the uploaded bundle.
- Restore remains explicitly destructive and requires operator confirmation in the admin UI.

## Administrative Safeguards

- Household membership changes and household deletion are audit logged.
- Pantry blocks membership removals that would leave a household without an admin where that safeguard applies.
- Household deletion requires explicit confirmation of the target household name, plus an extra acknowledgement when deleting the final household.

## Scope

This milestone does not add SaaS backup automation or self-updating behaviour. Recovery remains operator-driven and local-installation focused.

## External Data Handling

- Pantry may fetch optional product enrichment data from Open Food Facts for barcode and name-based lookups.
- Open Food Facts data is community-contributed and treated as advisory metadata, not Pantry's canonical product identity.
- Pantry validates external URLs and stores only selected, product-facing fields instead of logging or persisting whole upstream payloads.
- Enrichment must be explicitly confirmed by a user before Pantry links it to a product.
