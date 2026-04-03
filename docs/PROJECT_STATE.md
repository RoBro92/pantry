# Project State

Updated: 2026-04-03

## What Exists

- Root monorepo scaffold with `apps/`, `packages/`, `infra/`, `docs/`, and gitignored `private-docs/`.
- `VERSION` set to `0.1.0` as the canonical application version.
- Docker Compose stack for web, API, worker, PostgreSQL, and Redis.
- Next.js web app with login, authenticated household flows, recipe/import/AI pages, authenticated location deep links, and platform admin pages for overview, AI, SMTP, diagnostics, and settings.
- Next.js web app with browser-based first-run setup, clearer empty states, version visibility, installation-console user and household provisioning, and role-aware pantry controls.
- FastAPI app with server-enforced auth, tenancy, pantry, recipe, import, AI, diagnostics, SMTP, and QR/location routes.
- FastAPI app with one-time setup routes plus platform-admin user, household, and membership management endpoints.
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

- Implemented Milestone 8 self-hosted product hardening, setup experience, UX polish, and release-readiness work.
- Added `/api/setup/status` and `/api/setup/bootstrap-platform-admin` plus a browser `/setup` flow for the first platform admin, with one-time server-side enforcement and immediate sign-in.
- Added installation-console flows for platform admins to create users, create households, and assign memberships without leaving the app.
- Tightened pantry structure permissions so only `household_admin` can create location groups, locations, and products, while day-to-day stock actions remain available to `household_user`.
- Improved login, dashboard, pantry, import, recipe, AI, and admin UX with clearer empty states, better validation/error messages, and more explicit guidance for unconfigured or unhealthy installation features.
- Expanded Docker-backed Playwright coverage to include first-run setup and platform-admin provisioning flows, including a UI-level check that a normal household user cannot administer pantry structure.
- Updated public docs for the supported self-hosted setup path and recorded that host-side web build commands require Node 20 / npm 10, while the Docker web container remains the canonical validation runtime.

## Validation Results

- `cd apps/api && pytest tests/test_pantry_api.py tests/test_setup_api.py tests/test_platform_admin_api.py -q`: passed. `17 passed`.
- `cd apps/api && pytest tests/test_ai_api.py tests/test_import_api.py tests/test_recipe_api.py -q`: passed. `15 passed`.
- `cd apps/api && pytest -q`: passed. `37 passed`.
- `npm run typecheck:web`: passed.
- `npm run build:web`: failed on the host machine because this environment is `Node.js v25.6.1` / `npm 11.9.0`, which is outside the supported local runtime for the web toolchain.
- `docker compose up -d --build`: passed.
- `docker compose run --rm api alembic upgrade head`: passed.
- `./infra/scripts/smoke-check.sh`: passed.
- `./infra/scripts/e2e-seed.sh`: passed.
- `npm run test:e2e`: passed. `9 passed`.
- `docker compose exec -T web sh -lc 'node -v && npm -v && npm run build --workspace @pantry/web'`: passed under `Node.js v20.20.0` / `npm 10.8.2`.
- `docker compose down`: pending until the milestone close-out step at the end of this session.

## Blockers / Gaps

- Host-side web build commands currently require `Node.js 20.x` and `npm 10.x`. The local Docker web container already uses that runtime, but unsupported host runtimes can fail before app code is evaluated.
- Quota checks are still intentionally non-enforcing. Usage counters exist, but no user-visible limits or operator-configurable enforcement exist yet.
- Demo mode remains configuration-only. There is no demo reset, data wipe, or showcase orchestration system.
- Recipe URL import processing is still intentionally lightweight and depends on structured metadata such as JSON-LD rather than heavy scraping or browser automation.
- SMTP remains a foundation-only surface. There are still no invitation, password-recovery, or notification delivery workflows.
- Pantry structure edit/archive flows and richer household lifecycle tooling are still limited; the new provisioning UX covers first-use creation, not full long-term admin operations.

## Recommended Next Milestone

Milestone 9 should focus on shopping and day-to-day pantry workflow completion: shopping lists, deliberate consumption/replenishment flows, and the highest-value links between pantry coverage, recipe gaps, and household purchasing.

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
docker compose exec -T web sh -lc 'npm run build --workspace @pantry/web'
docker compose down
docker compose run --rm api python -m app.cli bootstrap-platform-admin --email admin@example.com
docker compose run --rm api python -m app.cli reset-password --email admin@example.com
```
