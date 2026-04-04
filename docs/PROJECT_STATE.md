# Project State

Updated: 2026-04-04

## What Exists

- Root monorepo scaffold with `apps/`, `packages/`, `infra/`, `docs/`, and gitignored `private-docs/`.
- `VERSION` set to `0.1.0` as the canonical application version.
- Docker Compose stack for web, API, worker, PostgreSQL, and Redis.
- Public self-hosted deployment assets: `infra/compose/pantry.yml`, `infra/env/pantry.env.example`, and operator scripts for install, update, and health verification.
- Production Dockerfiles for versioned GHCR image publishing.
- Next.js web app with login, authenticated household flows, recipe/import/AI pages, authenticated location deep links, and platform admin pages for overview, AI, SMTP, diagnostics, and settings.
- Next.js web app with browser-based first-run setup, clearer empty states, version visibility, and installation-console user and household provisioning.
- FastAPI app with server-enforced auth, tenancy, pantry, recipe, import, AI, diagnostics, SMTP, and QR/location routes.
- FastAPI app with one-time setup routes plus platform-admin user, household, and membership management endpoints.
- Python worker with import processing, recipe URL import processing, structured logging, and Redis-backed heartbeat publishing.
- SQLAlchemy models plus Alembic migrations for identity, tenancy, pantry, recipes, reviewed imports, AI provider config, instance settings, feature flags, and usage counters.
- Docker-backed Playwright E2E coverage for critical self-hosted flows.
- Advisory GitHub Releases-based update-check foundations for platform admins.
- Live tag-driven GitHub Actions release workflow for multi-arch GHCR publishing and GitHub Release creation or update.

## Assumptions In This Pass

- Self-hosted remains the primary supported mode in the public repository.
- `demo` and `saas` remain boundary markers and future extension points, not shipped public product variants.
- Hosted operations, billing, support tooling, and private runbooks belong outside this repository.
- Multi-tenant safety remains a non-negotiable requirement across API routes, services, jobs, and admin flows.

## Validation Workflow

- `docs/TEST_STRATEGY.md` defines the required local validation order and exact commands.
- Milestone work is not considered complete without recorded validation results, blockers, and next steps here.
- Docker-backed validation must start the stack when needed and shut it down afterward.

## Latest Change

- Replaced the old public `production.yml` and `production.lxc.env.example` asset names with `infra/compose/pantry.yml` and `infra/env/pantry.env.example`.
- Added public self-hosted operator scripts for install, update, and health verification, targeted at a fresh Debian LXC and versioned GHCR images.
- Added maintainer release scripts plus a live GitHub Actions workflow that validates the release, publishes multi-arch GHCR images, and creates or updates the GitHub Release.
- Updated README, deployment, versioning, file-map, decisions, and milestone docs to describe the conventional self-hosted Docker install and update flow.

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
- Release, versioning, GitHub Releases advisory checks, self-hosted install assets, and live GHCR publishing automation are now implemented.

### Partial Or Foundation-Only

- Recipe URL imports exist, but processing remains intentionally lightweight and depends on structured metadata rather than heavy scraping or browser automation.
- AI is intentionally advisory-only. Provider configuration, health, and read-only suggestions exist, but broader AI-assisted workflows do not.
- SMTP is a readiness and configuration surface with connectivity testing, not a shipped invitation or password-recovery system.
- Deployment modes, feature flags, demo mode, and usage counters exist as server-side primitives, but quota enforcement and demo automation do not.
- Broader rollback guidance and operator release checklists are still lighter than a mature product would want.

### Missing For The Planned Self-Hosted Release Path

- Shopping lists, purchase tracking, and deliberate consumption or replenishment workflows.
- Broader self-hosted release packaging such as fuller rollback guidance and an operator-facing release checklist.

### Deferred Intentionally

- Hosted billing, supporter logic, and SaaS tenant lifecycle implementation.
- Hosted AI routing or any hosted-only provider behavior.
- Demo reset and disposable-data lifecycle automation.
- Public hosted control-plane or support tooling.

## Validation Results

- `bash -n infra/scripts/release-manifest.sh infra/scripts/check-release-metadata.sh infra/scripts/install-pantry.sh infra/scripts/update-pantry.sh infra/scripts/healthcheck-pantry.sh infra/scripts/validate-release.sh infra/scripts/bump-version.sh infra/scripts/tag-release.sh infra/scripts/lib/pantry-selfhost.sh`: passed.
- `./infra/scripts/release-manifest.sh`: passed.
- `docker compose --env-file infra/env/pantry.env.example -f infra/compose/pantry.yml config`: passed.
- `cd apps/api && pytest tests/test_release_updates.py tests/test_platform_admin_api.py -q`: passed.
- `./infra/scripts/validate-release.sh`: passed.
- `python3 - <<'PY' ... yaml.safe_load('.github/workflows/release.yml') ... PY`: passed.
- `ruby -e 'require "yaml"; YAML.load_file(".github/workflows/release.yml")'`: passed.

## Blockers And Gaps

- Host-side web commands remain pinned to `Node.js 20.x` and `npm 10.x`. This pass documents and reinforces that requirement, but does not change the underlying Next.js compatibility boundary.
- Public GHCR packages must remain visible and the repository must allow Actions package publishing for the release workflow to succeed.
- Shopping and broader household lifecycle workflows remain the largest functional gap for a more complete self-hosted release.
- The Debian-LXC installer flow was validated through shell parsing, compose rendering, and shared helper reuse in this workspace, but not executed end-to-end on an actual fresh Debian LXC during this pass.

## Recommended Next Milestone

The next implementation-focused pass should tackle Milestone 9: shopping and daily household workflows. The self-hosted install and release path is now conventional enough for a public Docker application, and the largest remaining product gap is still the day-to-day household workflow layer.

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
docker compose --env-file infra/env/pantry.env.example -f infra/compose/pantry.yml config
./infra/scripts/validate-release.sh
docker compose down
docker compose run --rm api python -m app.cli bootstrap-platform-admin --email admin@example.com
docker compose run --rm api python -m app.cli reset-password --email admin@example.com
```
