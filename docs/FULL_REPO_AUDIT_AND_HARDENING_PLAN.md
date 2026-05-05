# Full Repository Audit And Hardening Plan

Date: 2026-05-05

Scope: Pantro v0.2.x Next.js web app, FastAPI API, Python worker, PostgreSQL, Redis, and Docker Compose self-hosted deployment path.

## Executive Summary

Pantro is in a workable v0.2.x state, but the audit found several security and production-readiness issues that should be closed before broader distribution. No confirmed critical issue was found. The highest-risk confirmed issues were SSRF in recipe URL imports, unsafe backup/import path trust during restore, broad web API proxying, open redirect handling on login, weak production secret defaults, and health checks that did not prove database or Redis readiness.

The first hardening pass fixed the confirmed high-risk issues that were practical to address without changing product direction. The follow-up pass added Redis-backed rate limiting with a local fallback, session-version revocation, direct API Origin/Referer protection, deterministic and live queue-claim tests, stronger smoke/e2e script preflights, and modal focus/Escape behavior. Docker demo smoke, full Playwright e2e, and live PostgreSQL queue contention validation have now been run locally. Remaining risks are mostly hosted-readiness items: centralized authorization policy, observability, support tooling, non-root container hardening, and broader abuse/egress controls.

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
- [x] Fixed: queue double-claim risk. Import, recipe URL import, and product intelligence claim queries now use `FOR UPDATE SKIP LOCKED` on PostgreSQL, with static SQL tests and live PostgreSQL contention tests run against the Docker Postgres service.
- [x] Fixed: Redis clients were not closed after heartbeat/health calls. `apps/api/app/services/runtime_status.py` now closes clients in `finally` blocks.
- [x] Fixed: failed-login/password reset rate limiting. `apps/api/app/services/rate_limits.py` uses Redis when available and falls back to an in-process window when Redis is unavailable.
- [x] Fixed: setup mutation rate limiting. First-run setup mutation routes now share a Redis-backed limiter.
- [x] Fixed: password reset/change did not revoke existing signed-cookie sessions. Users now have `session_version`, stored sessions carry the version, and credential/security-sensitive changes rotate it.
- [x] Fixed: direct API CSRF/origin protection. Unsafe API methods now require an allowed `Origin` or `Referer`, using `WEB_APP_URL`, `API_BASE_URL`, and `CSRF_TRUSTED_ORIGINS`.

### Low

- [x] Fixed: self-hosted backup storage was not mounted in production Compose. `BACKUP_STORAGE_ROOT` and `PANTRO_BACKUPS_DATA_DIR` are now represented in production compose/env examples.
- [x] Fixed: production web image used `npm install`. It now uses `npm ci`.
- [x] Fixed: frontend household pages lacked route-level prechecks. Household routes now call `requireHouseholdAccess` before loading household data.
- [x] Fixed: no app-level error boundary. A minimal `apps/web/app/error.tsx` was added.
- [x] Fixed: modal focus trapping and Escape-key behavior. `ModalShell` now moves focus into dialogs, traps Tab, closes on Escape, and restores focus.
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
- [x] Fixed: worker queue claims are safer and have deterministic static plus live PostgreSQL tests for multi-worker contention and stale-job reclaim.
- [x] Fixed: smoke/e2e scripts now have clearer preflight, timeout, readiness, migration-head, Redis, Postgres, and worker checks where practical.
- [ ] Not fixed: API startup still does not run migrations automatically. This is acceptable for self-hosting if the migrate step remains explicit and documented.
- [x] Fixed: e2e/smoke validation against the running Docker demo stack has been performed.

## SaaS-Readiness Findings

Do not add hosted-only logic or billing in this repo now. SaaS readiness should remain incremental:

- Keep household/tenant access checks explicit and tested.
- Add quotas/rate limits before public hosted access.
- Add abuse controls for outbound URL fetches, AI provider usage, SMTP, and restore uploads.
- Add operator/support views for job state, tenant activity, and provider health before hosted support.
- Add observability around request IDs, job IDs, provider request IDs, and sanitized error classes.
- Add secret rotation strategy before multi-tenant hosting.

## Test Coverage Gaps

- Live PostgreSQL concurrency tests for `SKIP LOCKED` queue claims now run when `PANTRY_TEST_POSTGRES_URL` points at a disposable PostgreSQL database; they passed against the Docker Postgres service in this validation pass.
- Browser e2e/smoke validation now runs against the local Docker demo stack; `CI=1 npm run test:e2e` passed with the suite's existing skipped test.
- Browser modal focus/accessibility specs execute against Docker-backed e2e seeding and passed.
- Broader frontend interaction tests for mobile layout and API error states remain limited.
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
- [x] Add rate limiting for auth/password reset flows.
- [x] Add setup mutation rate limiting.
- [x] Add session revocation/session-versioning for password changes, resets, and email changes.
- [x] Add direct API CSRF/origin protection.
- [x] Add PostgreSQL multi-worker queue contention tests, gated on `PANTRY_TEST_POSTGRES_URL`, and run them against Docker Postgres.
- [x] Add dialog/accessibility regression tests for modal focus, focus restoration, and Escape behavior.
- [x] Add live Docker smoke/e2e validation once Docker is available.

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
- Redis-backed auth/setup rate limiting.
- Session-version revocation.
- Direct API CSRF/origin checks.
- Smoke/e2e readiness script preflight improvements.
- Modal focus/Escape behavior.

## Fix Later

- Central authorization policy matrix and tests for every household route.
- Broader structured observability and support tooling.
- Broader frontend interaction regression coverage beyond modal focus.
- Explicit non-root image/runtime hardening once tested against the base images.

## Do Not Do Yet

- Do not add billing, subscription logic, or hosted-only assumptions.
- Do not split into native/mobile products.
- Do not replace the DB-backed queues with a separate queue architecture without evidence that v0.2.x needs it.
- Do not rewrite the backup service, product intelligence service, or frontend state model for style reasons alone.
- Do not remove self-hosted compatibility or legacy Pantry naming support before a planned migration window.

## Files And Areas Affected

- Backend security/runtime: `apps/api/app/core/config.py`, `apps/api/app/main.py`, `apps/api/app/api/routes/health.py`, `apps/api/app/api/routes/setup.py`
- Auth hardening: `apps/api/app/api/deps/auth.py`, `apps/api/app/api/routes/auth.py`, `apps/api/app/models/user.py`, `apps/api/app/services/auth.py`, `apps/api/app/services/password_resets.py`, `apps/api/app/services/rate_limits.py`, `apps/api/app/services/csrf.py`, `apps/api/alembic/versions/20260505_000022_user_session_version.py`
- Backup/import safety: `apps/api/app/services/backups.py`, `apps/api/app/services/import_storage.py`
- URL import safety: `apps/api/app/services/network_policy.py`, `apps/api/app/services/recipe_catalog.py`, `apps/api/app/services/recipe_url_imports.py`
- Queue/runtime stability: `apps/api/app/services/import_processing.py`, `apps/api/app/services/product_intelligence_runs.py`, `apps/api/app/services/runtime_status.py`
- Backend tests: `apps/api/tests/test_security_hardening.py`, `apps/api/tests/test_auth_security_hardening.py`, `apps/api/tests/test_queue_concurrency.py`
- Frontend security: `apps/web/app/api/[...path]/route.ts`, `apps/web/lib/proxy-policy.ts`, `apps/web/lib/redirect-path.ts`, `apps/web/lib/server-auth.ts`, `apps/web/lib/security-helpers.test.mjs`
- Frontend routes: `apps/web/app/(auth)/login/page.tsx`, household pages under `apps/web/app/(dashboard)/app/households/[householdExternalId]`, `apps/web/app/error.tsx`
- Frontend accessibility: `apps/web/components/modal-shell.tsx`, `tests/e2e/dialog-accessibility.spec.ts`
- Ops/deployment: `infra/compose/pantro.yml`, `infra/compose/pantry.yml`, `infra/env/*.env.example`, `infra/scripts/healthcheck-pantro.sh`, `infra/scripts/install-pantro.sh`, `infra/scripts/update-pantro.sh`, `infra/scripts/smoke-check.sh`, `infra/scripts/e2e-seed.sh`, `infra/scripts/e2e-reset-uninitialized.sh`, `infra/scripts/worker-once.sh`, `infra/docker/web.production.Dockerfile`, `docs/TEST_STRATEGY.md`, `docs/DEPLOYMENT.md`

## Investigated But Not Confirmed

- No confirmed household IDOR in sampled API service paths; API dependency checks are present, but more route-matrix tests are still warranted.
- No confirmed SQL injection in reviewed paths; SQLAlchemy expressions/ORM are used in the relevant flows.
- No confirmed command injection in reviewed scripts or app routes.
- No confirmed unsafe prompt/provider response logging of API keys; provider logging should still stay sanitized as observability grows.
- QR-code SVG/XSS risk was not confirmed in this pass.
- Direct public API CSRF/origin protection was implemented. Further review is still warranted for non-browser API automation that intentionally omits `Origin`/`Referer`.

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

## Follow-Up Changes Completed

- Added Redis-backed rate limiting for failed login attempts, password reset requests, and setup mutation routes, with in-process fallback when Redis is unavailable.
- Added non-enumerating `429` responses for login and password reset throttling.
- Added `users.session_version`, session-version storage in signed sessions, and rotation after password reset, password change, and email changes.
- Added direct API Origin/Referer protection for unsafe API methods, plus `CSRF_TRUSTED_ORIGINS` and rate-limit environment settings.
- Updated Next.js API proxy and Playwright helpers so normal web/API usage sends an allowed Origin.
- Added PostgreSQL queue contention tests gated by `PANTRY_TEST_POSTGRES_URL`, plus static PostgreSQL SQL compilation checks for `FOR UPDATE SKIP LOCKED`.
- Improved smoke/e2e helper scripts and documented local smoke/e2e prerequisites and commands.
- Improved modal focus handling, Tab trapping, Escape close behavior, and focus restoration; added Playwright regression specs.
- Started Docker Desktop locally, brought up `./pantro start --demo`, fixed live e2e blockers found by the full suite, and reran smoke/e2e successfully.
- Updated e2e reset behavior to clear Redis rate-limit keys so auth/setup throttles do not leak between deterministic test reseeds.
- Updated login rate limiting so successful logins do not consume failed-attempt budget and do not clear the shared IP failure bucket.
- Added authenticated web-proxy client-scope forwarding with `INTERNAL_API_PROXY_TOKEN` so rate-limit buckets do not collapse to the web container peer address.
- Allowed the setup SMTP connectivity-test route through the web API proxy.
- Updated the web API proxy to compare CSRF origins against the public request host/proto instead of the internal Next dev bind address.
- Updated modal autofocus handling so dialogs can mark their expected initial focus target.
- Marked the long shopping reconciliation e2e scenario as slow after Docker/Next dev memory restart timing exhausted the default 60-second test budget while the target page had already rendered.

## Test Evidence

- Passed: `pytest -q` in `apps/api` (`225 passed, 6 skipped in 55.69s`).
- Passed: `pytest tests/test_security_hardening.py -q` in `apps/api` (`15 passed`).
- Passed: targeted review-comment regression tests for auth/setup proxy scope, setup SMTP proxy access, and staged-backup path validation (`15 passed`).
- Passed: `pytest tests/test_queue_concurrency.py -q -rs` (`3 passed, 6 skipped`; static SQL checks without live PostgreSQL).
- Passed: `PANTRY_TEST_POSTGRES_URL='postgresql+psycopg://pantro:change-me@localhost:5432/pantro' pytest tests/test_queue_concurrency.py -q -rs` (`9 passed`) against the Docker Postgres service.
- Passed: targeted restore regression tests in `apps/api` (`5 passed`).
- Passed: `node --test apps/web/lib/security-helpers.test.mjs` (`5 passed`).
- Passed: `npm run typecheck:web`.
- Passed: `npm run build:web`.
- Passed: `CI=1 npx playwright test tests/e2e/dialog-accessibility.spec.ts` (`2 passed`).
- Passed: `CI=1 npx playwright test tests/e2e/core-flows.spec.ts -g "shopping reconciliation uses dense rows"` (`1 passed`).
- Passed: `CI=1 npm run test:e2e` (`29 passed, 1 skipped in 3.3m`) against the local Docker demo stack.
- Passed: `alembic heads` (`20260505_000022 (head)`).
- Passed: `DATABASE_URL=sqlite:////tmp/pantry-followup-migration-check.db alembic upgrade head`.
- Passed: `docker compose --profile manual --env-file infra/env/pantro.env.example -f infra/compose/pantro.yml config --quiet`.
- Passed: `docker compose --profile manual --env-file infra/env/pantry.env.example -f infra/compose/pantry.yml config --quiet`.
- Passed: `bash -n infra/scripts/*.sh infra/scripts/lib/*.sh`.
- Passed: `./pantro start --demo`.
- Passed: `./infra/scripts/smoke-check.sh`.
- Passed: `git diff --check`.

## What Could Not Be Tested

- No Docker/local-stack validation gap remains from this pass. Docker Desktop was started successfully and the demo stack, smoke check, full Playwright e2e, and live PostgreSQL queue tests were run.

## Issues Not Fixed

- Broader frontend interaction/accessibility tests beyond the shared modal regressions.
- Full observability/support tooling for hosted-style operations.

## Manual Follow-Up Required

- Review whether production containers should run as explicit non-root users in the published images.
- Review whether `/api/ready` should become the documented operator readiness endpoint for all install paths.

## Suggested Next Codex Prompt

Continue from `docs/FULL_REPO_AUDIT_AND_HARDENING_PLAN.md`. Docker smoke/e2e and live PostgreSQL queue tests have passed. Proceed to the remaining production hardening items only: explicit non-root container runtime evaluation, structured observability/support tooling, and a broader authorization route matrix. Do not add billing, hosted-only assumptions, or unrelated refactors.
