# Security

Security needs to shape the architecture before feature depth arrives.

## Core Threat Boundaries

- Uploaded files and import sources.
- Authentication and password recovery flows.
- Tenant isolation across households.
- AI provider credentials and external API access.
- QR-code deep links that expose location URLs.

## Security Rules

- Treat all uploads as hostile input.
- Never log secrets, tokens, passwords, or credential-bearing URLs.
- Enforce tenant scoping on the server for every household-owned resource.
- Use opaque external IDs for tenant-facing entities.
- Keep audit events for sensitive domain actions.
- Store import uploads outside any web-served path.
- Validate upload size and type in the application before worker processing.
- Reject credential-bearing provider base URLs and never return raw provider secrets after save.
- Encrypt stored provider secrets at rest for self-hosted deployments.
- Encrypt stored SMTP passwords at rest and never return them in plaintext after save.
- Require authenticated, server-scoped access checks before a QR/deep-link location route reveals household data.
- Keep platform diagnostics useful but secret-safe: no passwords, tokens, or fabricated host metrics.

## Logging Guidance

- Structured system logs are for runtime diagnostics.
- Audit events are for accountable business actions.
- Do not store raw secrets in either.
- Do not log prompt payloads that would expose secrets or credential-bearing URLs.

## Deferred Security Work

- CSRF/session hardening details.
- File scanning and stronger quarantine/isolation details beyond the current storage and status foundation.
- Secret rotation and backup policies for hosted environments.
