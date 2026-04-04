# Architecture

## High-Level Shape

Pantry is organized as a monorepo with separate runtime services:

- `apps/web`: browser-facing Next.js application.
- `apps/api`: FastAPI service for auth, pantry, recipe, and reviewed import APIs with server-enforced household access.
- `apps/worker`: background job processor for queued imports, future AI tasks, notifications, and other deferred work.
- `packages/shared-types`: lightweight shared TypeScript definitions for frontend-facing constants.

## Supporting Infrastructure

- PostgreSQL stores durable application data.
- Redis supports background work coordination, caching, and ephemeral state where needed.
- Docker Compose provides the local self-hosted development stack.
- Reverse proxy, TLS termination, and external ingress are outside the application boundary.

## Core Architecture Rules

- Tenant scoping is enforced server-side in the API layer and any worker jobs operating on tenant data.
- Web components remain presentation-focused; business rules stay in API or dedicated client-side domain modules.
- Pantry coverage, ingredient matching, and shopping-gap derivation live in API-side recipe services so household logic stays deterministic and server-enforced.
- Upload ingestion is isolated, stored outside web-served paths, and never treated as trusted input.
- Import extraction and review stay separate from pantry writes; explicit confirmation is the only path that creates stock lots from imports.
- Audit events are durable business records, distinct from runtime logs.
- AI provider calls go through adapters, not through core domain services directly.
- Installation-level SMTP, browser-link settings, and diagnostics remain API-owned concerns rather than being embedded in the web layer.
- First-run bootstrap state and installation provisioning remain API-owned concerns, with the web app acting only as the browser client for setup and admin flows.
- Release metadata and future update-available checks should remain API- or server-owned concerns so self-hosted admin UI does not depend on browser-side release scraping or secret-bearing requests.
- Deployment modes, feature flags, and usage counters are resolved and enforced in API-side services so future hosted differences do not leak into presentational UI.
- QR/browser deep links must resolve tenant access on the server before revealing household-scoped location data.

## Future SaaS Readiness

The public repo covers self-hosted and shared architecture concerns. SaaS operational details such as billing workflows, support tooling, secret rotation practices, or hosted runbooks belong in local-only `private-docs/` or a future private SaaS repository.

## Release And Update Boundaries

- `VERSION` remains the canonical application version in the repository.
- Runtime services should receive version data through environment variables derived from `VERSION`, with API and worker falling back to reading the repo `VERSION` file directly when needed.
- Container image publishing and GitHub Release publication are external delivery concerns, not runtime business logic.
- Self-hosted update notifications are API-owned, informational, and operator-driven; deployment automation and unattended upgrades are out of scope for now.
- Production deployment assets should pin released images explicitly and run migrations as a deliberate operator action rather than an automatic startup side effect.
