# Project State

Updated: 2026-04-04

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

- Reworked the roadmap so self-hosted completion, release workflow, production deployment, and later SaaS work are clearly separated.
- Added release/version/update planning docs centered on `VERSION`, GHCR image publishing, GitHub Releases metadata, and manual operator-driven updates.
- Recorded an explicit implementation audit covering complete, partial, missing, and intentionally deferred areas.
- Corrected stale docs that still described the repo as if auth, SQLAlchemy, and Alembic had not been selected or implemented.
- Added small release-aligned scaffolding so root web scripts export `NEXT_PUBLIC_APP_VERSION` from the canonical `VERSION` file.

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
- Current version visibility is already implemented in the landing page, authenticated shell, API health, and diagnostics surfaces.

### Partial / Foundation-Only

- Recipe URL imports exist, but processing is intentionally lightweight and depends on structured metadata rather than heavy scraping or browser automation.
- AI is intentionally advisory-only. Provider configuration, health, and read-only suggestions exist, but broader AI-assisted workflows do not.
- SMTP is a readiness/configuration surface with connectivity testing, not a shipped invitation or password-recovery system.
- Deployment modes, feature flags, demo mode, and usage counters exist as server-side primitives, but quota enforcement and demo automation do not.
- Release/version foundations exist through `VERSION`, environment injection, and current-version display, but release publication and update checks are not implemented yet.

### Missing For The Planned Self-Hosted Release Path

- Shopping lists, purchase tracking, and deliberate consumption/replenishment workflows.
- GHCR publishing workflow and GitHub Releases-based release/update metadata flow.
- Admin-visible update-available notification.
- Production deployment profile and LXC-focused deployment guidance beyond the current local Compose baseline.
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

- `npm run version:show`: passed.
- `sh -lc 'export NEXT_PUBLIC_APP_VERSION=$(./infra/scripts/read-version.sh); test "$NEXT_PUBLIC_APP_VERSION" = "$(cat VERSION)" && printf %s "$NEXT_PUBLIC_APP_VERSION"'`: passed.

Host-side `npm run typecheck:web` was not used as a final validation signal in this pass because `next typegen` again behaved unreliably under the local `Node.js v25.6.1` / `npm 11.9.0` environment. That behavior predates this docs pass and does not change the underlying release-planning conclusions.

This pass intentionally avoided Docker-backed validation because only docs and small release/version script scaffolding changed.

## Blockers / Gaps

- Host-side web commands remain pinned to `Node.js 20.x` and `npm 10.x`. This pass documents and reinforces that requirement, but does not change the underlying Next.js compatibility boundary.
- Release publishing, GHCR image automation, update-available checks, and production/LXC deployment packaging are still planned work rather than implemented features.
- Shopping and broader household lifecycle workflows remain the largest functional gap for a more complete self-hosted release.
- SMTP, AI, recipe URL import, demo mode, and quota handling remain intentionally partial foundations as noted above.

## Recommended Next Milestone

The next implementation-focused pass should tackle release/version/update workflow and production deployment readiness together: GHCR image publishing, GitHub Releases metadata, admin update-notification foundations, and LXC-oriented deployment guidance or scaffolding.

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
