# Multi Tenancy

Pantry is multi-household from the beginning even in self-hosted mode.

## Tenant Boundary

- A `Household` is the primary tenant boundary.
- Most business data is household-owned.
- `platform_admin` is the only role that crosses tenant boundaries by design.

## Enforcement Principles

- Tenant scoping is never trusted from the client alone.
- Every API path handling household data must resolve and verify tenant access server-side.
- Workers must receive tenant context as explicit job input and re-check access assumptions before making changes.
- Internal numeric database IDs should not be exposed as household-facing identifiers.
- Household API access uses the household external ID plus the authenticated session to resolve membership on the server.
- `platform_admin` can cross tenant boundaries intentionally; non-platform users cannot.

## Why This Matters Early

Retrofitting tenancy later usually leaks internal assumptions into APIs, jobs, and UI routing. Starting with household isolation keeps the self-hosted path aligned with future hosted deployments.
