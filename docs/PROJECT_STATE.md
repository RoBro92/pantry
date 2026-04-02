# Project State

Updated: 2026-04-02

## What Exists

- Root monorepo scaffold with `apps/`, `packages/`, `infra/`, `docs/`, and `private-docs/`.
- `VERSION` set to `0.1.0` as the intended source of truth for release versioning.
- Docker Compose stack for web, API, worker, PostgreSQL, and Redis.
- Next.js web app with a login page, authenticated app shell, and initial platform admin pages.
- FastAPI app with health endpoint, auth/session endpoints, platform admin endpoints, and tenant-aware household access checks.
- FastAPI pantry core with household-scoped location groups, locations, products, aliases, barcodes, stock lots, aggregated pantry views, near-expiry queries, and pantry audit events.
- Minimal Python worker with config scaffold, structured logging, and placeholder status output.
- Shared TypeScript package with deployment modes, roles, and domain-entity constants.
- SQLAlchemy models plus Alembic migrations for identity, tenancy, pantry structure, stock lots, and audit events.
- Password hashing via Argon2 and signed cookie sessions for the web login foundation.
- CLI commands for first-platform-admin bootstrap and password reset.
- API tests covering login/session behavior, email normalization, tenant membership enforcement, and pantry add/remove/move behavior.
- Next.js pantry household page with creation controls, lot mutations, search/filtering, aggregated product totals, near-expiry view, and recent pantry activity.
- Updated documentation covering product direction, architecture, security, tenancy, deployment, testing, and contribution rules.
- Durable Codex operating instructions centered on `AGENTS.md`, with milestone validation policy in `docs/TEST_STRATEGY.md`.
- A repeatable local smoke-check helper at `infra/scripts/smoke-check.sh` for web, API, and worker baseline validation.

## Assumptions In This Pass

- Self-hosted local development is the primary near-term target.
- Docker Compose is the quickest path to a consistent developer environment.
- PostgreSQL is the system of record; Redis supports worker and transient coordination concerns.
- Signed cookie sessions are sufficient for the current self-hosted foundation and can be replaced later if revocation or multi-device controls need stronger guarantees.
- Pantry household members can perform routine pantry mutations; future milestones can decide whether finer-grained policy differences between household admins and household users are needed.
- Private SaaS and operations material will live only in local `private-docs/`.

## Validation Workflow

- `AGENTS.md` is now the durable instruction source for future Codex milestone work.
- `docs/TEST_STRATEGY.md` defines the required local validation order and exact commands.
- Milestone work is not considered complete without recorded validation results, blockers, and next steps here.
- Docker-backed smoke validation should start the stack when needed and shut it down afterward.

## Latest Change

- Added pantry-core persistence with models and migrations for `LocationGroup`, `Location`, `Product`, `ProductAlias`, `Barcode`, `StockLot`, and `AuditEvent`.
- Added household-scoped pantry API routes for pantry overview, near-expiry, location creation, product creation, stock-lot creation, stock removal, and stock moves.
- Added deterministic normalization for product names, aliases, and barcodes, plus lot-preserving move semantics that keep aggregate views derived from stock lots.
- Added a household pantry web page with search/filter controls, aggregated product totals, stock-lot actions, near-expiry view, and recent pantry activity.
- Added pantry API tests and updated docs so the milestone state, endpoint catalog, and durable decisions reflect Milestone 2 delivery.

## Validation Results

- `cd apps/api && pytest tests/test_pantry_api.py -q`: passed.
- `npm run typecheck:web`: passed.
- `cd apps/api && pytest -q`: passed.
- `npm run build:web`: passed.
- `docker compose up -d --build`: passed.
- `docker compose run --rm api alembic upgrade head`: passed.
- `./infra/scripts/smoke-check.sh`: passed.
- `docker compose down`: passed.

## Blockers / Gaps

- No dedicated E2E suite exists yet, so user-facing changes currently rely on targeted smoke checks plus service-specific tests.

## Recommended Next Milestone

Milestone 3 should implement:

- Import job lifecycle and persistence
- Source-file storage and hostile-upload validation
- Reviewable import lines and safe parsing workflow
- A worker-backed path for asynchronous import processing

## Useful Commands

```bash
docker compose up -d --build
docker compose run --rm api alembic upgrade head
./infra/scripts/smoke-check.sh
docker compose down
docker compose run --rm api python -m app.cli bootstrap-platform-admin --email admin@example.com
docker compose run --rm api python -m app.cli reset-password --email admin@example.com
python3 -m pip install -r apps/api/requirements-dev.txt
cd apps/api && pytest
cd apps/api && pytest tests/test_pantry_api.py -q
npm run typecheck:web
npm run build:web
```
