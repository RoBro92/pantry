# Project State

Updated: 2026-04-02

## What Exists

- Root monorepo scaffold with `apps/`, `packages/`, `infra/`, `docs/`, and `private-docs/`.
- `VERSION` set to `0.1.0` as the intended source of truth for release versioning.
- Docker Compose stack for web, API, worker, PostgreSQL, and Redis.
- Next.js web app with a login page, authenticated app shell, pantry pages, reviewed import pages, and platform admin pages.
- FastAPI app with health endpoint, auth/session endpoints, platform admin endpoints, tenant-aware household access checks, pantry routes, recipe routes, and reviewed import routes.
- FastAPI pantry core with household-scoped location groups, locations, products, aliases, barcodes, stock lots, aggregated pantry views, near-expiry queries, and pantry audit events.
- FastAPI recipe core with household-scoped recipes, ingredients, deterministic pantry-product matching, pantry coverage checks, shopping-gap calculation, and URL import capture foundations.
- FastAPI import core with household-scoped upload history, import detail, reviewable lines, deterministic matching, explicit confirm-to-pantry flows, and import audit coverage.
- Python worker with queued import processing, structured logging, deterministic parser foundations for JSON/CSV/TSV/text imports, and visible failure states for deferred PDF/image parsing.
- Shared TypeScript package with deployment modes, roles, and domain-entity constants.
- SQLAlchemy models plus Alembic migrations for identity, tenancy, pantry structure, stock lots, audit events, recipe records, and reviewed import records.
- Password hashing via Argon2 and signed cookie sessions for the web login foundation.
- CLI commands for first-platform-admin bootstrap and password reset.
- API tests covering login/session behavior, email normalization, tenant membership enforcement, pantry stock behavior, recipe flows, and import upload/review/confirm behavior.
- Updated documentation covering product direction, architecture, security, imports, observability, testing, and milestone sequencing.
- Durable Codex operating instructions centered on `AGENTS.md`, with milestone validation policy in `docs/TEST_STRATEGY.md`.
- A repeatable local smoke-check helper at `infra/scripts/smoke-check.sh` for web, API, and worker baseline validation.

## Assumptions In This Pass

- Self-hosted local development is the primary near-term target.
- Docker Compose remains the quickest path to a consistent developer environment.
- PostgreSQL is the system of record; Redis supports worker and transient coordination concerns.
- Signed cookie sessions are sufficient for the current self-hosted foundation and can be replaced later if revocation or multi-device controls need stronger guarantees.
- Pantry household members can perform routine pantry mutations; future milestones can decide whether finer-grained policy differences between household admins and household users are needed.
- Private SaaS and operations material will live only in local `private-docs/`.

## Validation Workflow

- `AGENTS.md` is the durable instruction source for future Codex milestone work.
- `docs/TEST_STRATEGY.md` defines the required local validation order and exact commands.
- Milestone work is not considered complete without recorded validation results, blockers, and next steps here.
- Docker-backed smoke validation should start the stack when needed and shut it down afterward.

## Latest Change

- Added reviewed import persistence with models and migration for `ImportJob`, `ImportSourceFile`, and `ImportLine`.
- Added safe upload storage foundations with application-level size/type validation, non-web storage paths, and future scan-status hooks.
- Added household-scoped import API routes for upload, history, detail, line review, ignore/update, and explicit confirm-to-pantry flows.
- Added worker-backed import processing for structured JSON, CSV, TSV, and plain-text inputs, with deterministic matching and visible failure states for deferred PDF/image parsing.
- Added import inbox/history and reviewed import detail pages in the web app, including line-level review controls and explicit confirmation into pantry stock lots.
- Updated roadmap/docs to mark Milestone 4 complete and shift the next milestone to AI provider abstraction and pantry-aware suggestion foundations.

## Validation Results

- `python3 -m pip install -r apps/api/requirements-dev.txt`: passed.
- `cd apps/api && pytest tests/test_import_api.py -q`: passed.
- `cd apps/api && pytest tests/test_pantry_api.py tests/test_recipe_api.py -q`: passed.
- `cd apps/api && pytest -q`: passed.
- `npm run typecheck:web`: passed.
- `npm run build:web`: passed.
- `docker compose up -d --build`: passed.
- `docker compose run --rm api alembic upgrade head`: passed.
- `./infra/scripts/smoke-check.sh`: passed.
- `docker compose exec -T api python - <<'PY' ... PY`: passed. Seeded a dedicated import-smoke household, pantry location, and pantry products in the running stack.
- `python3 - <<'PY' ... PY`: passed. Logged in through the live API, uploaded a structured import, forced worker execution with `docker compose exec -T worker python -m worker.main --once`, reviewed the unresolved line, confirmed the import into pantry stock, verified pantry lot creation, and confirmed web detail rendering at `/app/households/{household_external_id}/imports/{import_external_id}`.
- `docker compose down`: passed.

## Blockers / Gaps

- No dedicated E2E suite exists yet, so user-facing changes currently rely on targeted smoke checks plus service-specific tests.
- PDF/image imports are intentionally foundation-only in this pass: files are stored safely and tracked, but OCR/extraction is not implemented yet.
- Recipe URL import remains capture-only; it has not yet been moved onto the reviewed import worker path.

## Recommended Next Milestone

Milestone 5 should implement:

- AI provider abstraction for local/self-hosted and OpenAI-compatible backends.
- Pantry-aware suggestion foundations that can plug into recipe and import review workflows.
- Feature-gated AI entrypoints without putting provider-specific logic into core domain services.

## Useful Commands

```bash
docker compose up -d --build
docker compose run --rm api alembic upgrade head
./infra/scripts/smoke-check.sh
docker compose exec -T worker python -m worker.main --once
docker compose down
docker compose run --rm api python -m app.cli bootstrap-platform-admin --email admin@example.com
docker compose run --rm api python -m app.cli reset-password --email admin@example.com
python3 -m pip install -r apps/api/requirements-dev.txt
cd apps/api && pytest
cd apps/api && pytest tests/test_import_api.py -q
cd apps/api && pytest tests/test_recipe_api.py -q
cd apps/api && pytest tests/test_pantry_api.py -q
npm run typecheck:web
npm run build:web
```
