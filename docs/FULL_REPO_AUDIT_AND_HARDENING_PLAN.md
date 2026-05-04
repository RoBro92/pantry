# Full Repository Audit And Hardening Plan

Date: 2026-05-05

Scope: Pantro v0.2.x Next.js web app, FastAPI API, Python worker, PostgreSQL, Redis, and Docker Compose self-hosted deployment path.

## Executive Summary

Pantro is in a workable v0.2.x state, but the audit found several security and production-readiness issues that should be closed before broader distribution. No confirmed critical issue was found. The highest-risk confirmed issues were SSRF in recipe URL imports, unsafe backup/import path trust during restore, broad web API proxying, open redirect handling on login, weak production secret defaults, and health checks that did not prove database or Redis readiness.

The first hardening pass fixed the confirmed high-risk issues that were practical to address without changing product direction. It also improved readiness checks, backup storage persistence, queue behavior, Redis client lifecycle, frontend auth guards, and production Docker install behavior. Remaining risks are mostly operational controls and hosted-readiness items: login/reset rate limiting, session revocation after password changes, centralized authorization policy, deeper worker concurrency tests, observability, and abuse/egress controls.

## Current Repo Condition

- Product shape is coherent: a single web product with self-hosted Docker Compose support.
- Service boundaries are mostly clear: Next.js web, FastAPI API, worker package reusing API services, PostgreSQL as durable state, Redis for worker heartbeat/runtime status.
- The backend has useful service-layer separation, but some service modules carry broad responsibilities, especially backups, pantry/product workflows, and product intelligence.
- Database access mostly uses SQLAlchemy expressions and ORM models. No confirmed ad hoc SQL injection issue was found in the reviewed paths.
- Frontend server components generally load data server-side, but household route pages were relying on downstream API checks rather than early route-level membership checks.
- Deployment scripts are useful for self-hosting, but production defaults previously assumed too much manual operator correctness.

## Major Risks

- Untrusted outbound fetch: recipe URL import could reach internal services or metadata endpoints.
- Restore/import trust boundary: backup bundles could include unsafe import source storage paths that a worker would later resolve from disk.
- Frontend proxy surface: the catch-all Next.js proxy previously forwarded broad API paths and unnecessary request/response headers.
- Production readiness signal: `/api/health` was static and could report healthy when Postgres, Redis, or migrations were not ready.
- Weak secret defaults: production could start with placeholder or shared secrets, and encrypted provider settings could fall back to the session secret.
- Queue reliability: some DB-backed queues could leave jobs stuck or double-claimed under multi-worker pressure.

## Security Findings By Severity

### Critical

- None confirmed in this audit.

### High

- [x] Fixed: recipe URL import SSRF. `apps/api/app/services/network_policy.py`, `recipe_catalog.py`, and `recipe_url_imports.py` now reject local/private/reserved targets, validate redirect targets, cap redirects and response size, and require HTML responses.
- [x] Fixed: backup restore/import source path trust. `apps/api/app/services/import_storage.py` now validates relative storage paths and enforces resolved root containment; `apps/api/app/services/backups.py` now rejects unsafe `import_source_files.storage_path` values in bundles.
- [x] Fixed: staged backup path traversal. Backup stage IDs are restricted to generated 32-character hex IDs and staged file paths are resolved under the quarantine root.
- [x] Fixed: weak production secrets. `apps/api/app/core/config.py` now rejects placeholder, missing, too-short, or shared production session/settings encryption secrets.
- [x] Fixed: broad frontend API proxy and unsafe forwarded headers. `apps/web/app/api/[...path]/route.ts` now applies an allowlist, strips dangerous forwarded headers, strips internal response headers, and rejects cross-origin mutating requests.
- [x] Fixed: login `next` open redirect. `apps/web/lib/redirect-path.ts` only allows same-app single-slash internal paths.

### Medium

- [x] Fixed: setup mutation endpoints stayed callable after setup completion. `apps/api/app/api/routes/setup.py` now closes setup mutation/test/finalize routes once initialization is complete.
- [x] Fixed: health check was only liveness. `apps/api/app/api/routes/health.py` now adds `/api/ready` with database, migration, and Redis checks while leaving `/api/health` as liveness.
- [x] Fixed: DB engine lifecycle. `apps/api/app/main.py` now disposes the SQLAlchemy engine during FastAPI shutdown.
- [x] Fixed: import jobs could stay stuck after a worker crash. `_claim_next_import_job` can reclaim stale processing jobs and uses PostgreSQL row locking where supported.
- [x] Partially fixed: queue double-claim risk. Import, recipe URL import, and product intelligence claim queries now use `FOR UPDATE SKIP LOCKED` on PostgreSQL. Remaining gap: no load/concurrency test was run against a live PostgreSQL stack.
- [x] Fixed: Redis clients were not closed after heartbeat/health calls. `apps/api/app/services/runtime_status.py` now closes clients in `finally` blocks.
- [ ] Not fixed: login/password reset rate limiting. Needs a durable limiter strategy for self-hosted and future hosted deployments.
- [ ] Not fixed: password reset/change does not revoke existing signed-cookie sessions. Requires a server-side session version or revocation model.
- [ ] Not fixed: CSRF is mitigated at the web proxy origin check, but API-wide CSRF policy is not centralized for all possible direct API deployments.

### Low

- [x] Fixed: self-hosted backup storage was not mounted in production Compose. `BACKUP_STORAGE_ROOT` and `PANTRO_BACKUPS_DATA_DIR` are now represented in production compose/env examples.
- [x] Fixed: production web image used `npm install`. It now uses `npm ci`.
- [x] Fixed: frontend household pages lacked route-level prechecks. Household routes now call `requireHouseholdAccess` before loading household data.
- [x] Fixed: no app-level error boundary. A minimal `apps/web/app/error.tsx` was added.
- [ ] Not fixed: modal focus trapping and Escape-key behavior should be reviewed across dialogs.
- [ ] Not fixed: Docker images still run as image defaults. Compose adds `no-new-privileges` and drops capabilities, but explicit non-root runtime users should be evaluated per image.

## Maintainability Findings By Priority

- High: backup service is large and mixes serialization, compatibility, staging, and restore application. Avoid a speculative rewrite now, but split only when fixing concrete restore bugs.
- High: authorization is mostly enforced in API dependencies, with some frontend route checks now added. A central policy/testing matrix would reduce IDOR regression risk.
- Medium: frontend API call handling is split between server and client helpers with different error behavior. Standardize user-facing error parsing and retry behavior incrementally.
- Medium: product intelligence service has substantial orchestration, retry, diagnostics, and persistence logic in one module. Keep current behavior stable before extracting smaller units.
- Medium: worker and API share API service modules. This is pragmatic now, but runtime-only worker concerns should stay out of request handlers.
- Low: self-host scripts contain compatibility fallbacks and legacy Pantry/Pantro naming support. Keep until the v0.2.x transition is complete.

## Production-Readiness Findings

- [x] Fixed: `/api/ready` checks DB connectivity, Alembic head parity, and Redis health.
- [x] Fixed: production Compose API healthchecks prefer `/api/ready` with `/api/health` fallback for older images.
- [x] Fixed: production Compose mounts import and backup storage into API/migrate and import storage into worker.
- [x] Fixed: migration service now mounts the same storage roots used by API restore flows.
- [x] Fixed: install/update healthcheck scripts understand readiness checks.
- [x] Fixed: Redis heartbeat helpers close clients.
- [x] Partially fixed: worker queue claims are safer, but live multi-worker PostgreSQL contention was not exercised because Docker was unavailable.
- [ ] Not fixed: API startup still does not run migrations automatically. This is acceptable for self-hosting if the migrate step remains explicit and documented.
- [ ] Not fixed: e2e/smoke validation against a running local stack could not be performed because the Docker daemon was not available.

## SaaS-Readiness Findings

Do not add hosted-only logic or billing in this repo now. SaaS readiness should remain incremental:

- Keep household/tenant access checks explicit and tested.
- Add quotas/rate limits before public hosted access.
- Add abuse controls for outbound URL fetches, AI provider usage, SMTP, and restore uploads.
- Add operator/support views for job state, tenant activity, and provider health before hosted support.
- Add observability around request IDs, job IDs, provider request IDs, and sanitized error classes.
- Add secret rotation/session revocation strategy before multi-tenant hosting.

## Test Coverage Gaps

- No live PostgreSQL concurrency test for `SKIP LOCKED` queue claims.
- No browser e2e/smoke run in this pass because Docker was unavailable.
- No rate-limit tests because rate limiting is not implemented yet.
- No session revocation tests because signed-cookie revocation is not implemented yet.
- Limited frontend interaction tests for dialogs, focus management, mobile layout, and API error states.
- Backup restore tests cover API behavior, but not a full production-volume restore with API/worker containers sharing mounted storage.

## Recommended Target Architecture/State

- Preserve a single web product with self-hosted Compose as the primary v0.2.x operator path.
- Keep Next.js as the browser-facing surface and restrict the web API proxy to known frontend paths.
- Keep FastAPI as the authoritative authorization and validation boundary.
- Keep DB-backed queues for v0.2.x, but use row locks, stale-job reclaiming, and diagnostics before introducing a separate queue system.
- Keep Redis for runtime heartbeat/status unless and until durable queue semantics are intentionally introduced.
- Treat backup/restore as a privileged administrative workflow with staged quarantine, strict JSON validation, explicit confirmation phrases, and shared persistent storage.
- Treat SaaS readiness as hardening primitives only: tenant boundaries, quotas, observability, support tooling, and abuse controls.

## Prioritised Action Plan

- [x] Audit repository architecture, security, production readiness, frontend/backend quality, and deployment.
- [x] Fix confirmed high security issues: SSRF, unsafe restore path trust, frontend proxy/header surface, login open redirect, weak production secrets.
- [x] Fix setup flow abuse after initialization.
- [x] Add readiness checks and update production healthcheck wiring.
- [x] Persist backup storage in production Compose/env examples.
- [x] Improve worker queue claim safety and Redis lifecycle.
- [x] Add focused backend and frontend tests for the hardening fixes.
- [x] Run backend tests, frontend tests/typecheck/build, migration checks, and Compose config validation.
- [ ] Add rate limiting for auth/password reset flows.
- [ ] Add session revocation/session-versioning for password changes and resets.
- [ ] Add live Docker smoke/e2e validation once Docker is available.
- [ ] Add PostgreSQL multi-worker queue contention tests.
- [ ] Add dialog/accessibility and mobile regression tests for key frontend flows.

## Fix Now

- URL import SSRF controls.
- Restore/import storage path validation.
- Backup stage ID path validation.
- Production secret validation.
- Web proxy allowlist/header filtering/cross-origin mutation checks.
- Login redirect validation.
- Setup mutation closure after initialization.
- Readiness checks and production healthcheck wiring.
- Persistent backup storage mounts.
- Queue stale-job reclaiming and Redis client closure.

## Fix Later

- Login/password reset rate limiting.
- Server-side session versioning/revocation.
- Central authorization policy matrix and tests for every household route.
- Live PostgreSQL queue contention tests.
- Broader structured observability and support tooling.
- Dialog focus management and frontend interaction regression coverage.
- Explicit non-root image/runtime hardening once tested against the base images.

## Do Not Do Yet

- Do not add billing, subscription logic, or hosted-only assumptions.
- Do not split into native/mobile products.
- Do not replace the DB-backed queues with a separate queue architecture without evidence that v0.2.x needs it.
- Do not rewrite the backup service, product intelligence service, or frontend state model for style reasons alone.
- Do not remove self-hosted compatibility or legacy Pantry naming support before a planned migration window.

## Files And Areas Affected

- Backend security/runtime: `apps/api/app/core/config.py`, `apps/api/app/main.py`, `apps/api/app/api/routes/health.py`, `apps/api/app/api/routes/setup.py`
- Backup/import safety: `apps/api/app/services/backups.py`, `apps/api/app/services/import_storage.py`
- URL import safety: `apps/api/app/services/network_policy.py`, `apps/api/app/services/recipe_catalog.py`, `apps/api/app/services/recipe_url_imports.py`
- Queue/runtime stability: `apps/api/app/services/import_processing.py`, `apps/api/app/services/product_intelligence_runs.py`, `apps/api/app/services/runtime_status.py`
- Backend tests: `apps/api/tests/test_security_hardening.py`
- Frontend security: `apps/web/app/api/[...path]/route.ts`, `apps/web/lib/proxy-policy.ts`, `apps/web/lib/redirect-path.ts`, `apps/web/lib/server-auth.ts`, `apps/web/lib/security-helpers.test.mjs`
- Frontend routes: `apps/web/app/(auth)/login/page.tsx`, household pages under `apps/web/app/(dashboard)/app/households/[householdExternalId]`, `apps/web/app/error.tsx`
- Ops/deployment: `infra/compose/pantro.yml`, `infra/compose/pantry.yml`, `infra/env/*.env.example`, `infra/scripts/healthcheck-pantro.sh`, `infra/scripts/install-pantro.sh`, `infra/scripts/update-pantro.sh`, `infra/docker/web.production.Dockerfile`

## Investigated But Not Confirmed

- No confirmed household IDOR in sampled API service paths; API dependency checks are present, but more route-matrix tests are still warranted.
- No confirmed SQL injection in reviewed paths; SQLAlchemy expressions/ORM are used in the relevant flows.
- No confirmed command injection in reviewed scripts or app routes.
- No confirmed unsafe prompt/provider response logging of API keys; provider logging should still stay sanitized as observability grows.
- QR-code SVG/XSS risk was not confirmed in this pass.
- Direct public API CSRF risk depends on deployment topology; the web proxy now blocks cross-origin mutations, but API-wide policy remains a future hardening item.

## Risky Changes To Avoid

- Avoid automatic destructive restore behavior or implicit merge semantics.
- Avoid auto-running migrations inside every API boot without an operator-approved rollout model.
- Avoid adding a new queue/broker abstraction until DB-backed queues are proven inadequate.
- Avoid making hosted/SaaS assumptions in config names, user model, or product flows.
- Avoid large module splits unless paired with a tested behavior fix.

## Changes Completed In This Pass

- Fixed SSRF protection for recipe URL import, including redirects and private DNS/IP targets.
- Fixed unsafe import source path handling in restore bundles and import storage resolution.
- Fixed backup stage ID traversal and symlinked temp-root path handling.
- Added production secret validation and startup failure for weak production config.
- Added readiness endpoint and shutdown DB engine disposal.
- Closed setup mutation endpoints after initialization.
- Reclaimed stale import jobs and added PostgreSQL row locking to import, recipe URL, and product intelligence claims.
- Closed Redis clients after heartbeat/readiness operations.
- Hardened the web API proxy, redirect handling, and frontend household auth prechecks.
- Added a minimal frontend error boundary.
- Hardened production Compose/env/script/Dockerfile behavior through PR branch changes.

## Test Evidence

- Passed: `pytest -q` in `apps/api` (`209 passed in 48.26s`).
- Passed: `pytest tests/test_security_hardening.py -q` in `apps/api` (`15 passed`).
- Passed: targeted restore regression tests in `apps/api` (`5 passed`).
- Passed: `node --test apps/web/lib/security-helpers.test.mjs` (`5 passed`).
- Passed: `npm run typecheck:web`.
- Passed: `npm run build:web`.
- Passed: `alembic heads` (`20260419_000021 (head)`).
- Passed: `DATABASE_URL=sqlite:////tmp/pantry-audit-migration-check.db alembic upgrade head`.
- Passed: `docker compose --profile manual --env-file infra/env/pantro.env.example -f infra/compose/pantro.yml config --quiet`.
- Passed: `docker compose --profile manual --env-file infra/env/pantry.env.example -f infra/compose/pantry.yml config --quiet`.
- Passed: `bash -n infra/scripts/healthcheck-pantro.sh infra/scripts/install-pantro.sh infra/scripts/update-pantro.sh`.
- Passed: `git diff --check`.
- Not run: live Docker stack health check, smoke check, demo seed, and Playwright e2e. Docker daemon was unavailable at `unix:///Users/robinbrown/.docker/run/docker.sock`.

## Issues Not Fixed

- Auth/password reset rate limiting.
- Session revocation after password reset/change.
- API-wide CSRF policy for direct API deployments.
- Full PostgreSQL concurrency tests for DB queues.
- Full local-stack smoke/e2e validation.
- Broader frontend dialog accessibility tests.
- Full observability/support tooling for hosted-style operations.

## Manual Follow-Up Required

- Decide the rate-limit storage strategy: Redis-backed limits are preferable for multi-process deployments.
- Decide whether to introduce server-side session versioning in the user table to revoke signed-cookie sessions.
- Run `npm run dev:stack:demo`, `infra/scripts/smoke-check.sh`, and `npm run test:e2e` once Docker is available.
- Review whether production containers should run as explicit non-root users in the published images.
- Review whether `/api/ready` should become the documented operator readiness endpoint for all install paths.

## Suggested Next Codex Prompt

Continue from `docs/FULL_REPO_AUDIT_AND_HARDENING_PLAN.md`. Implement the remaining auth hardening items in priority order: Redis-backed login/password-reset rate limiting, session-version revocation after password reset/change, and API-wide CSRF/origin policy for direct API deployments. Keep self-hosted support, add focused tests first, and run backend/frontend validation plus Docker smoke/e2e if Docker is available.
