# Project State

Updated: 2026-04-02

## What Exists

- Root monorepo scaffold with `apps/`, `packages/`, `infra/`, `docs/`, and `private-docs/`.
- `VERSION` set to `0.1.0` as the intended source of truth for release versioning.
- Docker Compose stack for web, API, worker, PostgreSQL, and Redis.
- Minimal Next.js web app with a status-oriented landing page and future route group.
- Minimal FastAPI app with health endpoint, config scaffold, and structured request logging.
- Minimal Python worker with config scaffold, structured logging, and placeholder status output.
- Shared TypeScript package with deployment modes, roles, and domain-entity constants.
- Initial documentation set covering product direction, architecture, security, tenancy, deployment, testing, and contribution rules.

## Assumptions In This Pass

- Self-hosted local development is the primary near-term target.
- Docker Compose is the quickest path to a consistent developer environment.
- PostgreSQL is the system of record; Redis supports worker and transient coordination concerns.
- Auth, persistence, and business workflows are intentionally deferred to Milestone 1 and beyond.
- Private SaaS and operations material will live only in local `private-docs/`.

## Recommended Next Milestone

Milestone 1 should implement:

- Users
- Households
- Memberships
- Roles
- Login and session auth
- Admin bootstrap CLI
- Password reset CLI
- Initial admin shell pages

That milestone should also introduce the first database migrations, server-side tenant scoping, and an audit-event write path for identity and membership changes.

