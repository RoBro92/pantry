# Project State

Updated: 2026-04-03

## What Exists

- Root monorepo scaffold with `apps/`, `packages/`, `infra/`, `docs/`, and gitignored `private-docs/`.
- `VERSION` set to `0.1.0` as the canonical application version.
- Docker Compose stack for web, API, worker, PostgreSQL, and Redis.
- Next.js web app with login, authenticated household flows, recipe/import/AI pages, authenticated location deep links, and platform admin pages for overview, AI, SMTP, diagnostics, and settings.
- FastAPI app with server-enforced auth, tenancy, pantry, recipe, import, AI, diagnostics, SMTP, and QR/location routes.
- Python worker with import processing, recipe URL import processing, structured logging, and Redis-backed heartbeat publishing.
- SQLAlchemy models plus Alembic migrations for identity, tenancy, pantry, recipes, reviewed imports, AI provider config, instance settings, feature flags, and usage counters.
- Docker-backed Playwright E2E coverage for critical self-hosted flows.
- Shared deployment-mode constants normalized to `self_hosted`, `demo`, and `saas`.
- Server-side feature-flag resolution and request metering foundations with non-enforcing quota checks.

## Assumptions In This Pass

- Self-hosted remains the primary supported mode in the public repository.
- `demo` and `saas` are boundary markers and future extension points, not shipped public product variants.
- Hosted operations, billing, support tooling, and private runbooks belong outside this repository.
- Multi-tenant safety remains a non-negotiable requirement across API routes, services, jobs, and admin flows.

## Validation Workflow

- `docs/TEST_STRATEGY.md` defines the required local validation order and exact commands.
- Milestone work is not considered complete without recorded validation results, blockers, and next steps here.
- Docker-backed validation must start the stack when needed and shut it down afterward.

## Latest Change

- Added the first real Playwright E2E suite with deterministic Docker-backed seeding and worker helpers.
- Closed deferred gaps in recipe URL imports, import-line validation, AI runtime failure handling, and SMTP config validation.
- Removed internal prompt/Codex-specific docs from the public repository and kept them only in local `private-docs/`.
- Added validated deployment-mode support for `self_hosted`, `demo`, and `saas`, plus server-side `FeatureFlag` and `UsageCounter` foundations.
- Removed public UI exposure of future hosted modes from the landing page while preserving SaaS-readiness primitives behind server boundaries.
- Fixed a worker-image dependency gap discovered during milestone validation by adding `httpx` and `pydantic` to `apps/worker/requirements.txt`.

## Validation Results

- `npm install`: passed.
- `python3 -m pip install -r apps/api/requirements-dev.txt`: passed.
- `npx playwright install chromium`: passed.
- `docker compose up -d --build`: passed.
- `docker compose run --rm api alembic upgrade head`: passed.
- `cd apps/api && pytest -q`: passed. `30 passed`.
- `npm run typecheck:web`: passed.
- `npm run build:web`: passed.
- `./infra/scripts/smoke-check.sh`: initially failed because the worker image was missing `httpx` for the new recipe URL-import worker path; after updating worker dependencies and rebuilding, passed.
- `./infra/scripts/e2e-seed.sh`: passed.
- `npm run test:e2e`: passed. `7 passed`.
- `docker compose down`: passed.

## Blockers / Gaps

- `saas` mode is still a placeholder only. There is no hosted billing, onboarding, support tooling, or SaaS-specific UI in this repository.
- Quota checks are intentionally non-enforcing in this milestone. Usage counters exist, but no limits are being applied yet.
- Demo mode is configuration-only. There is no demo reset, wipe, or preview-orchestration system.
- Recipe URL import processing is intentionally lightweight and currently depends on structured metadata such as JSON-LD; heavy scraping, OCR, or browser automation is still deferred.
- SMTP remains a foundation-only surface. There are still no invitation, password-recovery, or notification delivery workflows.

## Recommended Next Milestone

Milestone 8 should set up the separate private SaaS repository and formalize the boundary between this public self-hosted codebase and hosted-only operations. That pass should focus on repository separation, shared contract extraction, and ownership rules rather than adding public-repo SaaS product behavior.

## Useful Commands

```bash
npm install
npx playwright install chromium
python3 -m pip install -r apps/api/requirements-dev.txt
docker compose up -d --build
docker compose run --rm api alembic upgrade head
cd apps/api && pytest -q
npm run typecheck:web
npm run build:web
./infra/scripts/smoke-check.sh
./infra/scripts/e2e-seed.sh
npm run test:e2e
docker compose down
docker compose run --rm api python -m app.cli bootstrap-platform-admin --email admin@example.com
docker compose run --rm api python -m app.cli reset-password --email admin@example.com
```
