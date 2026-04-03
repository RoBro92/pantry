# Project State

Updated: 2026-04-02

## What Exists

- Root monorepo scaffold with `apps/`, `packages/`, `infra/`, `docs/`, and `private-docs/`.
- `VERSION` set to `0.1.0` as the intended source of truth for release versioning.
- Docker Compose stack for web, API, worker, PostgreSQL, and Redis.
- Next.js web app with a login page, authenticated app shell, pantry pages, reviewed import pages, authenticated location deep-link pages, and platform admin pages for overview, AI, SMTP, diagnostics, and settings.
- FastAPI app with health endpoint, auth/session endpoints, platform admin endpoints, diagnostics/settings/SMTP routes, tenant-aware household access checks, pantry routes, recipe routes, reviewed import routes, and authenticated location-link routes.
- FastAPI pantry core with household-scoped location groups, locations, products, aliases, barcodes, stock lots, aggregated pantry views, near-expiry queries, and pantry audit events.
- FastAPI recipe core with household-scoped recipes, ingredients, deterministic pantry-product matching, pantry coverage checks, shopping-gap calculation, and URL import capture foundations.
- FastAPI import core with household-scoped upload history, import detail, reviewable lines, deterministic matching, explicit confirm-to-pantry flows, and import audit coverage.
- FastAPI AI core with instance-scoped provider configuration, encrypted secret-at-rest handling, Ollama and OpenAI-compatible adapters, provider health metadata, household AI status endpoints, and read-only pantry-aware suggestion entrypoints.
- FastAPI instance settings foundation with installation-scoped public/browser base URL handling, SMTP readiness configuration, encrypted SMTP password storage, and env-overridable effective config resolution.
- FastAPI diagnostics coverage for measurable app uptime, worker heartbeat, Redis reachability, queue counts, database health/size, entity counts, AI summary, SMTP summary, and browser-link settings.
- Python worker with queued import processing, structured logging, deterministic parser foundations for JSON/CSV/TSV/text imports, visible failure states for deferred PDF/image parsing, and Redis-backed heartbeat publishing for diagnostics.
- Shared TypeScript package with deployment modes, roles, and domain-entity constants.
- SQLAlchemy models plus Alembic migrations for identity, tenancy, pantry structure, stock lots, audit events, recipe records, and reviewed import records.
- Password hashing via Argon2 and signed cookie sessions for the web login foundation.
- CLI commands for first-platform-admin bootstrap and password reset.
- API tests covering login/session behavior, email normalization, tenant membership enforcement, pantry stock behavior, recipe flows, import upload/review/confirm behavior, diagnostics, SMTP redaction, and QR/location-link behavior.
- Updated documentation covering product direction, architecture, AI integration, security, imports, observability, testing, and milestone sequencing.
- Milestone validation policy documented in `docs/TEST_STRATEGY.md`, with local-only internal notes kept outside the public repo.
- A repeatable local smoke-check helper at `infra/scripts/smoke-check.sh` for web, API, and worker baseline validation.

## Assumptions In This Pass

- Self-hosted local development is the primary near-term target.
- Docker Compose remains the quickest path to a consistent developer environment.
- PostgreSQL is the system of record; Redis supports worker and transient coordination concerns.
- Signed cookie sessions are sufficient for the current self-hosted foundation and can be replaced later if revocation or multi-device controls need stronger guarantees.
- Pantry household members can perform routine pantry mutations; future milestones can decide whether finer-grained policy differences between household admins and household users are needed.
- Private SaaS and operations material will live only in local `private-docs/`.

## Validation Workflow

- `docs/TEST_STRATEGY.md` defines the required local validation order and exact commands.
- Milestone work is not considered complete without recorded validation results, blockers, and next steps here.
- Docker-backed smoke validation should start the stack when needed and shut it down afterward.

## Latest Change

- Added `InstanceSetting` persistence with a matching Alembic migration for installation-scoped public/browser base URL and SMTP foundation settings.
- Added platform admin settings, SMTP, and diagnostics API routes with encrypted SMTP password storage, password redaction, lightweight SMTP connectivity testing, and a real-data-only diagnostics report.
- Added Redis-backed worker heartbeat publishing so the API can report worker status without fabricating container metrics.
- Added pantry location deep-link metadata in pantry responses, an authenticated `/api/locations/{location_route}` API route, and a Next.js `/locations/[locationRoute]` browser route for QR flows.
- Added inline server-rendered pantry location QR codes in the web app plus admin console navigation/pages for overview, AI, SMTP, diagnostics, and settings.
- Updated roadmap/docs to mark Milestone 6 foundation work complete and point the next milestone toward a SaaS-readiness pass with feature-flag, quota, demo-mode, and E2E foundations.

## Validation Results

- `cd apps/api && pytest tests/test_platform_admin_api.py -q`: passed.
- `cd apps/api && pytest -q`: passed.
- `npm run typecheck:web`: passed.
- `npm run build:web`: passed.
- `docker compose up -d --build`: passed.
- `docker compose run --rm api alembic upgrade head`: passed.
- `./infra/scripts/smoke-check.sh`: passed.
- `docker compose exec -T api python - <<'PY' ... PY`: passed. Seeded a dedicated Milestone 6 smoke platform admin, household member, household, and pantry location in the running stack.
- `python3 - <<'PY' ... PY`: passed. Logged in through the live API, verified the admin diagnostics web page loaded, updated the public/browser base URL through the admin API, confirmed the pantry overview location QR link switched to the new base URL, and verified the authenticated `/locations/{locationRoute}` web route resolved successfully.
- `docker compose down`: passed.

## Blockers / Gaps

- No dedicated E2E suite exists yet, so user-facing changes currently rely on targeted smoke checks plus service-specific tests.
- No live SMTP server was available in the local validation stack, so SMTP connectivity behavior is covered by focused API tests and route wiring rather than an end-to-end mail transport.
- Household-level AI provider override records are not enabled yet, though the persistence and resolution shape leaves room for that follow-up without replacing the API surface.
- AI suggestions remain advisory-only, and SMTP remains a foundation-only capability; there are still no full notification/invite flows, chatbot surfaces, or async AI job orchestration.

## Recommended Next Milestone

Milestone 7 should implement:

- SaaS-readiness cleanup across deployment modes and platform boundaries.
- Feature-flag and usage/quota skeletons.
- Demo-mode skeleton.
- The first real E2E suite for the most important self-hosted user flows if it is still missing.

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
cd apps/api && pytest tests/test_platform_admin_api.py -q
npm run typecheck:web
npm run build:web
```
