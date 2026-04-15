# Security

Pantry treats uploads, restore bundles, and external data as hostile input until they have been validated.

## Reporting A Vulnerability

- Do not post exploit details, credentials, or sensitive deployment data in a public issue
- If GitHub private vulnerability reporting is enabled for this repository, use that channel
- If no private reporting channel is available, open a minimal public issue requesting a private contact path without including sensitive details
- Reproduce against the latest release when it is safe to do so, but do not delay reporting a credible security issue

## Data And Access Boundaries

- Household scoped access is enforced server side
- Pantry records remain Pantry owned even when external enrichment is attached
- Sensitive configuration persisted by the application is intended to be encrypted at rest
- Secrets, tokens, and passwords should never be committed to the repository

## Backup And Restore Safety

- Restore accepts Pantry backup bundle JSON files only
- Uploads are validated before restore is allowed
- Uploaded restore files are staged under `BACKUP_STORAGE_ROOT`
- Restore remains an explicit operator action because it can replace live data
- Household restore creates a new household only and does not merge into an existing one

## External Data Handling

- Open Food Facts lookup is optional
- External enrichment is advisory metadata, not Pantry’s canonical product record
- Pantry stores selected product facing enrichment fields instead of treating upstream payloads as trusted source data

## Operational Safety

- Keep `.env` out of version control
- Back up PostgreSQL data and import storage before upgrades
- Review new environment templates during upgrades instead of assuming old values still match
- Use the bundled health check after installs and updates
- Self-service password reset should only be enabled after SMTP is configured and tested

## Scope

This repository documents Pantry’s application level safety model for the self-hosted, operator-managed product. Host hardening, TLS, backup retention, secret management, and patching remain operator responsibilities.
