# Security

Pantry handles household data, credentials, and uploaded files. The public repository follows a few fixed security rules.

## Core Rules

- Treat uploads and import sources as hostile input
- Enforce household-scoped access on the server for every household-owned resource
- Use opaque external IDs for tenant-facing objects
- Never log secrets, passwords, tokens, or credential-bearing URLs
- Store uploaded files outside web-served paths
- Keep sensitive configuration values encrypted at rest where the application persists them
- Require authenticated access checks before QR or deep-link location routes reveal household data

## Operational Guidance

- Run released images from trusted tags
- Keep `.env` out of version control
- Back up PostgreSQL data and import storage before upgrades
- Review new environment templates during upgrades instead of carrying assumptions forward unchanged
- Use the bundled health check after installs and updates

## Scope

This file is repository-level guidance, not a full hardening guide for every deployment environment. Reverse proxy, TLS, host patching, backups, and secret management remain operator responsibilities.
