# Project State

Updated: 2026-04-02

## What Exists

- Root monorepo scaffold with `apps/`, `packages/`, `infra/`, `docs/`, and `private-docs/`.
- `VERSION` set to `0.1.0` as the intended source of truth for release versioning.
- Docker Compose stack for web, API, worker, PostgreSQL, and Redis.
- Next.js web app with a login page, authenticated app shell, and initial platform admin pages.
- FastAPI app with health endpoint, auth/session endpoints, platform admin endpoints, and tenant-aware household access checks.
- Minimal Python worker with config scaffold, structured logging, and placeholder status output.
- Shared TypeScript package with deployment modes, roles, and domain-entity constants.
- SQLAlchemy models plus an Alembic migration for `Role`, `User`, `Household`, and `Membership`.
- Password hashing via Argon2 and signed cookie sessions for the web login foundation.
- CLI commands for first-platform-admin bootstrap and password reset.
- API tests covering login/session behavior, email normalization, and tenant membership enforcement.
- Updated documentation covering product direction, architecture, security, tenancy, deployment, testing, and contribution rules.

## Assumptions In This Pass

- Self-hosted local development is the primary near-term target.
- Docker Compose is the quickest path to a consistent developer environment.
- PostgreSQL is the system of record; Redis supports worker and transient coordination concerns.
- Signed cookie sessions are sufficient for the current self-hosted foundation and can be replaced later if revocation or multi-device controls need stronger guarantees.
- The current admin web surface is intentionally read-oriented; richer create/update flows can follow once Milestone 2 and beyond firm up operational patterns.
- Private SaaS and operations material will live only in local `private-docs/`.

## Recommended Next Milestone

Milestone 2 should implement:

- Location groups and locations
- Products, aliases, and stock lots
- Add, remove, and move stock flows
- Aggregated household inventory views
- Audit-event writes for inventory mutations

## Useful Commands

```bash
docker compose up --build
docker compose run --rm api python -m app.cli bootstrap-platform-admin --email admin@example.com
docker compose run --rm api python -m app.cli reset-password --email admin@example.com
python3 -m pip install -r apps/api/requirements-dev.txt
cd apps/api && pytest
```
