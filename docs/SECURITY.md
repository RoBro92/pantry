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

## Logging Guidance

- Structured system logs are for runtime diagnostics.
- Audit events are for accountable business actions.
- Do not store raw secrets in either.

## Deferred Security Work

- CSRF/session hardening details.
- File scanning and stronger quarantine/isolation details beyond the current storage and status foundation.
- Secret rotation and backup policies for hosted environments.
