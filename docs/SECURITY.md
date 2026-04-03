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
- Allow browser bootstrap of the first platform admin only while the install is still uninitialized.
- Store import uploads outside any web-served path.
- Validate upload size and type in the application before worker processing.
- Reject credential-bearing provider base URLs and never return raw provider secrets after save.
- Encrypt stored provider secrets at rest for self-hosted deployments.
- Encrypt stored SMTP passwords at rest and never return them in plaintext after save.
- Reject malformed SMTP host configuration such as embedded credentials, paths, query strings, or inline ports.
- Require authenticated, server-scoped access checks before a QR/deep-link location route reveals household data.
- Restrict pantry structure changes such as location-group, location, and product creation to `household_admin` on the server even when the UI hides those actions from `household_user`.
- Keep platform diagnostics useful but secret-safe: no passwords, tokens, or fabricated host metrics.
- Keep request metering and future quota foundations server-side, keyed by route templates and scoped identifiers rather than raw URLs or secret-bearing payloads.
- Keep hosted-only operational details, runbooks, and support mechanics out of the public repo.

## Logging Guidance

- Structured system logs are for runtime diagnostics.
- Audit events are for accountable business actions.
- Do not store raw secrets in either.
- Do not log prompt payloads that would expose secrets or credential-bearing URLs.
- Do not log raw SMTP or provider connection strings if they include credentials.

## Deferred Security Work

- CSRF/session hardening details.
- File scanning and stronger quarantine/isolation details beyond the current storage and status foundation.
- Secret rotation and backup policies for hosted environments.
- Real quota enforcement and hosted abuse throttling policies.
