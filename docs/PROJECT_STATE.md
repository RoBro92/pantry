# Project State

Updated: 2026-04-04

## What Exists

- Root monorepo scaffold with `apps/`, `packages/`, `infra/`, `docs/`, and gitignored `private-docs/`.
- `VERSION` set to `0.1.0` as the canonical application version.
- Docker Compose stack for web, API, worker, PostgreSQL, and Redis.
- Production Compose, production Dockerfiles, and an LXC-oriented env template for pinned-image self-hosted deployment.
- Next.js web app with login, authenticated household flows, recipe/import/AI pages, authenticated location deep links, and platform admin pages for overview, AI, SMTP, diagnostics, and settings.
- Next.js web app with browser-based first-run setup, clearer empty states, version visibility, installation-console user and household provisioning, and role-aware pantry controls.
- FastAPI app with server-enforced auth, tenancy, pantry, recipe, import, AI, diagnostics, SMTP, and QR/location routes.
- FastAPI app with one-time setup routes plus platform-admin user, household, and membership management endpoints.
- Python worker with import processing, recipe URL import processing, structured logging, and Redis-backed heartbeat publishing.
- SQLAlchemy models plus Alembic migrations for identity, tenancy, pantry, recipes, reviewed imports, AI provider config, instance settings, feature flags, and usage counters.
- Docker-backed Playwright E2E coverage for critical self-hosted flows.
- Advisory GitHub Releases-based update-check foundation for platform admins.
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

- Removed the remaining hardcoded real-version fallback in the web app so `VERSION` stays the only canonical release value.
- Added API-owned advisory update-check foundations using GitHub Releases latest metadata, including admin overview and diagnostics visibility plus graceful unavailable and not-configured states.
- Bound the running version into structured API and worker log context so logs, worker heartbeat, diagnostics, and UI surfaces all report version consistently.
- Added production deployment assets for Docker on LXC: production Dockerfiles, pinned-image production compose, an operator env template, and lightweight release/update helper scaffolding.
- Updated release, deployment, architecture, file-map, roadmap, and README docs to reflect the new self-hosted operator workflow.

## Implementation Audit

### Complete

- Identity, tenancy, and session auth foundations from Milestones 0-1 are implemented and validated in code.
- Pantry structure, stock-lot tracking, recent pantry activity, and role-aware household access from Milestone 2 are implemented.
- Recipe CRUD, deterministic pantry matching, coverage calculation, and shopping-gap derivation from Milestone 3 are implemented.
- Reviewed import upload, line review, worker processing, and confirm-to-pantry flow from Milestone 4 are implemented.
- Installation-scoped AI provider configuration, health handling, and read-only household suggestion flow from Milestone 5 are implemented.
- Diagnostics, SMTP readiness foundation, public browser URL handling, QR/location links, and admin navigation from Milestone 6 are implemented.
- SaaS-readiness primitives from Milestone 7 are implemented as boundaries only: deployment modes, feature flags, usage counters, and E2E foundations.
- First-run setup, admin provisioning, permission tightening, UX hardening, and expanded E2E coverage from Milestone 8 are implemented.
- Current version visibility is now implemented in the landing page, authenticated shell, admin overview, API health, diagnostics, worker heartbeat, and structured service logs.

### Partial / Foundation-Only

- Recipe URL imports exist, but processing is intentionally lightweight and depends on structured metadata rather than heavy scraping or browser automation.
- AI is intentionally advisory-only. Provider configuration, health, and read-only suggestions exist, but broader AI-assisted workflows do not.
- SMTP is a readiness/configuration surface with connectivity testing, not a shipped invitation or password-recovery system.
- Deployment modes, feature flags, demo mode, and usage counters exist as server-side primitives, but quota enforcement and demo automation do not.
- Release/version foundations now include GitHub Releases-based advisory update checks plus production deployment scaffolding, but live publishing automation is still not active in the repo.

### Missing For The Planned Self-Hosted Release Path

- Shopping lists, purchase tracking, and deliberate consumption/replenishment workflows.
- Live GHCR publishing workflow and active GitHub Release automation.
- Broader self-hosted release packaging such as upgrade/rollback guidance and operator-facing release checklist.

### Deferred Intentionally

- Hosted billing, supporter logic, and SaaS tenant lifecycle implementation.
- Hosted AI routing or any hosted-only provider behavior.
- Demo reset/disposable-data lifecycle automation.
- Public hosted-control-plane or support tooling.

## Docs / Code Mismatches Corrected In This Pass

- `docs/TECH_STACK.md` previously claimed the repo had not selected an ORM, migration tool, or auth/session approach. That was stale and is now corrected.
- `docs/FUTURE_SCOPE.md` previously claimed there was no auth implementation yet. That was stale and is now corrected.
- The roadmap previously placed SaaS-oriented work too early and did not track release/version/update flow, production/LXC deployment, or later UI refinement explicitly.
- Version visibility existed in code but was under-documented. The release/version docs now track those existing surfaces clearly.

## Validation Results

- `cd apps/api && pytest tests/test_release_updates.py tests/test_platform_admin_api.py -q`: passed.
- `bash -n infra/scripts/release-manifest.sh infra/scripts/check-release-metadata.sh`: passed.
- `./infra/scripts/release-manifest.sh`: passed.
- `docker compose --env-file infra/env/production.lxc.env.example -f infra/compose/production.yml config`: passed.
- `docker compose up -d --build`: passed.
- `docker compose run --rm api alembic upgrade head`: passed.
- `./infra/scripts/smoke-check.sh`: passed after rerunning cleanly without competing writes to the shared web `.next` volume.
- `npx playwright test tests/e2e/core-flows.spec.ts -g 'platform admin diagnostics page loads against the docker stack'`: passed.
- `docker build -f infra/docker/api.production.Dockerfile -t pantry-api-production:test .`: passed.
- `docker build -f infra/docker/worker.production.Dockerfile -t pantry-worker-production:test .`: passed.
- `docker build -f infra/docker/web.production.Dockerfile --build-arg NEXT_PUBLIC_APP_VERSION=$(cat VERSION) -t pantry-web-production:test .`: passed.

Host-side `npm run typecheck:web` still was not used as a final validation signal because `next typegen` remains unreliable under the local `Node.js v25.6.1` / `npm 11.9.0` environment. The Dockerized production web build now provides the Node 20 validation signal for the changed admin UI and version/update plumbing.

`docker compose exec -T web sh -lc 'export NEXT_PUBLIC_APP_VERSION=$(cat /workspace/VERSION) && npm run build --workspace @pantry/web'` was not kept as the final web-build signal because running it alongside the live dev server caused `.next` manifest contention inside the shared volume. Re-running validation through the production Docker build avoided that false-negative path cleanly.

## Blockers / Gaps

- Host-side web commands remain pinned to `Node.js 20.x` and `npm 10.x`. This pass documents and reinforces that requirement, but does not change the underlying Next.js compatibility boundary.
- Live GHCR and GitHub Release automation are still scaffolding and docs rather than active CI workflows.
- Shopping and broader household lifecycle workflows remain the largest functional gap for a more complete self-hosted release.
- SMTP, AI, recipe URL import, demo mode, and quota handling remain intentionally partial foundations as noted above.

## Recommended Next Milestone

The next implementation-focused pass should tackle Milestone 9: shopping and daily household workflows. The self-hosted release and deployment foundation is materially stronger now, and the largest remaining product gap is the day-to-day household workflow layer.

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
docker compose --env-file infra/env/production.lxc.env.example -f infra/compose/production.yml config
docker build -f infra/docker/web.production.Dockerfile --build-arg NEXT_PUBLIC_APP_VERSION=$(cat VERSION) -t pantry-web-production:test .
docker compose down
docker compose run --rm api python -m app.cli bootstrap-platform-admin --email admin@example.com
docker compose run --rm api python -m app.cli reset-password --email admin@example.com
```
