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
- FastAPI AI core with instance-scoped provider configuration, encrypted secret-at-rest handling, Ollama and OpenAI-compatible adapters, provider health metadata, household AI status endpoints, and read-only pantry-aware suggestion entrypoints.
- Python worker with queued import processing, structured logging, deterministic parser foundations for JSON/CSV/TSV/text imports, and visible failure states for deferred PDF/image parsing.
- Shared TypeScript package with deployment modes, roles, and domain-entity constants.
- SQLAlchemy models plus Alembic migrations for identity, tenancy, pantry structure, stock lots, audit events, recipe records, and reviewed import records.
- Password hashing via Argon2 and signed cookie sessions for the web login foundation.
- CLI commands for first-platform-admin bootstrap and password reset.
- API tests covering login/session behavior, email normalization, tenant membership enforcement, pantry stock behavior, recipe flows, and import upload/review/confirm behavior.
- Updated documentation covering product direction, architecture, AI integration, security, imports, observability, testing, and milestone sequencing.
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

- Added `AIProviderConfig` persistence with a matching Alembic migration for instance-scoped AI provider configuration and future household overrides.
- Added encrypted-at-rest provider secret handling, deployment feature gating, provider health metadata, and adapter abstractions for Ollama and OpenAI-compatible APIs.
- Added platform admin AI configuration routes plus household AI status and read-only suggestion endpoints with structured pantry/recipe context assembly and JSON output contracts.
- Added structured AI request lifecycle logs and audit events for provider configuration changes plus user-triggered AI suggestion activity.
- Added a minimal admin AI provider page and a household AI suggestions page in the web app, including clean unavailable and unhealthy states.
- Updated roadmap/docs to mark Milestone 5 foundation work complete and point the next milestone toward platform admin diagnostics, SMTP, QR generation, and admin polish.

## Validation Results

- `cd apps/api && pytest tests/test_ai_api.py -q`: passed.
- `python3 -m pip install -r apps/api/requirements-dev.txt`: passed.
- `cd apps/api && pytest -q`: passed.
- `npm run typecheck:web`: passed.
- `npm run build:web`: passed.
- `docker compose up -d --build`: passed.
- `docker compose run --rm api alembic upgrade head`: passed.
- `./infra/scripts/smoke-check.sh`: passed.
- `docker compose exec -T api python - <<'PY' ... PY`: passed. Seeded a dedicated AI smoke platform admin, household member, and household in the running stack.
- `python3 - <<'PY' ... PY`: passed. Logged in through the live API, verified the household AI status endpoint returned a clean unconfigured response, saved an instance AI provider config through the admin API with a deliberately unreachable Ollama base URL, verified secrets were redacted in the response, confirmed household AI suggestion requests failed safely with `503`, and verified the household AI status endpoint moved to `health_status=unhealthy`.
- `docker compose down`: passed.

## Blockers / Gaps

- No dedicated E2E suite exists yet, so user-facing changes currently rely on targeted smoke checks plus service-specific tests.
- No live healthy AI provider was available in the local validation stack, so the configured healthy path is covered by focused API tests with a stub provider adapter rather than an end-to-end provider call.
- Household-level AI provider override records are not enabled yet, though the persistence and resolution shape leaves room for that follow-up without replacing the API surface.
- AI suggestions are intentionally advisory-only in this pass; they do not mutate pantry stock, recipes, imports, or shopping state, and no chatbot or async AI job orchestration exists yet.

## Recommended Next Milestone

Milestone 6 should implement:

- Platform admin diagnostics and operational visibility around the now-growing self-hosted surface.
- SMTP foundation for password recovery and future notifications.
- QR generation for pantry locations.
- Admin UX polish for the installation-level shell.

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
cd apps/api && pytest tests/test_ai_api.py -q
npm run typecheck:web
npm run build:web
```
