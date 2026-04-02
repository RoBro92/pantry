# Architecture

## High-Level Shape

Pantry is organized as a monorepo with separate runtime services:

- `apps/web`: browser-facing Next.js application.
- `apps/api`: FastAPI service for auth, domain APIs, household enforcement, and future imports.
- `apps/worker`: background job processor for imports, AI tasks, notifications, and deferred work.
- `packages/shared-types`: lightweight shared TypeScript definitions for frontend-facing constants.

## Supporting Infrastructure

- PostgreSQL stores durable application data.
- Redis supports background work coordination, caching, and ephemeral state where needed.
- Docker Compose provides the local self-hosted development stack.
- Reverse proxy, TLS termination, and external ingress are outside the application boundary.

## Core Architecture Rules

- Tenant scoping is enforced server-side in the API layer and any worker jobs operating on tenant data.
- Web components remain presentation-focused; business rules stay in API or dedicated client-side domain modules.
- Upload ingestion is isolated and never treated as trusted input.
- Audit events are durable business records, distinct from runtime logs.
- AI provider calls go through adapters, not through core domain services directly.

## Future SaaS Readiness

The public repo covers self-hosted and shared architecture concerns. SaaS operational details such as billing workflows, support tooling, secret rotation practices, or hosted runbooks belong in local-only `private-docs/`.

