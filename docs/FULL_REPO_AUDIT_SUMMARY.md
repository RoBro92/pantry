# Full Repo Audit Summary

Date: 2026-05-05

## What Was Found

No confirmed critical issue was found. The original high-risk confirmed issues included recipe URL SSRF, unsafe restore/import storage path trust, broad frontend API proxying, login open redirect handling, weak production secret defaults, and static health checks that did not verify Postgres, Redis, or migrations.

The follow-up review focused on the remaining security and production-readiness gaps: auth abuse throttling, session revocation, direct API CSRF/origin protection, queue contention coverage, Docker smoke/e2e readiness, and modal focus regressions.

## What Was Fixed

- Redis-backed rate limiting now protects failed login attempts, password reset request, and first-run setup mutation routes, with non-enumerating errors and an in-process fallback if Redis is unavailable.
- Password reset, password change, and email change now rotate `users.session_version`; old signed-cookie sessions are rejected and refreshed sessions continue to work.
- Unsafe direct API methods now require an allowed `Origin` or `Referer`; `WEB_APP_URL`, `API_BASE_URL`, and `CSRF_TRUSTED_ORIGINS` define the allowed self-hosted origins.
- PostgreSQL queue contention tests were added, including static `FOR UPDATE SKIP LOCKED` checks and gated live multi-worker/stale-reclaim tests behind `PANTRY_TEST_POSTGRES_URL`.
- Docker smoke/e2e helper scripts now perform clearer preflight/readiness checks for web, API, migration head, Redis, Postgres, and worker status where practical.
- Shared modal dialogs now move focus into the dialog, trap Tab, close on Escape, restore focus on close, and have Playwright regression coverage.
- Docker Desktop was started locally, the demo stack was rebuilt with `./pantro start --demo`, smoke checks passed, full Playwright e2e passed, and live PostgreSQL queue contention tests passed against the Docker Postgres service.
- E2E reset now clears Redis rate-limit keys so auth/setup throttles do not leak between deterministic reseeds.
- Login rate limiting now avoids consuming failure budget on successful logins and avoids clearing the shared IP failure bucket after a valid login.
- The web API proxy now compares CSRF origins against the public request host/proto instead of the internal Next dev bind address.
- Dialog autofocus targets are explicit for scanner-heavy modal flows.
- The long shopping reconciliation e2e scenario is marked slow to account for Docker/Next dev memory restart timing without relaxing its assertions.
- The earlier pass also fixed SSRF, restore path trust, production secret validation, `/api/ready`, web proxy/header hardening, login redirect validation, setup closure, stale queue reclaiming, Redis client closure, and production Compose/env hardening.

## What Was Not Fixed

- Explicit non-root container users, broader observability, quotas, abuse controls, and hosted-style support tooling remain future work.

## What Could Not Be Tested

- No Docker/local-stack validation gap remains from this pass. Docker demo startup, smoke checks, full Playwright e2e, dialog assertions, and live PostgreSQL queue contention tests were all run locally.

## Risk Remaining

The highest-risk self-hosted security gaps found in the audit are now reduced. Remaining risk is mostly operational maturity: direct API automation must send an allowed `Origin`/`Referer` or be intentionally configured, explicit non-root container runtime users still need evaluation, and hosted-readiness observability/support tooling remains future work.

Redis-backed rate limiting falls back to per-process in-memory limits if Redis is unavailable, which preserves throttling but is weaker than shared Redis limits in a horizontally scaled deployment.

## Tests Run

- `pytest -q` in `apps/api` (`222 passed, 6 skipped`).
- Targeted backend auth/security tests, including rate limits, session revocation, and CSRF: `33 passed`.
- Live PostgreSQL queue contention tests against Docker Postgres: `9 passed`.
- `node --test apps/web/lib/security-helpers.test.mjs`.
- `npm run typecheck:web` and `npm run build:web`.
- `CI=1 npx playwright test tests/e2e/dialog-accessibility.spec.ts` (`2 passed`).
- Targeted shopping reconciliation e2e regression: `1 passed`.
- `CI=1 npm run test:e2e` (`29 passed, 1 skipped in 2.7m`) against the local Docker demo stack.
- `./pantro start --demo` and `./infra/scripts/smoke-check.sh`.
- Alembic head and SQLite migration upgrade checks.
- Docker Compose config validation for Pantro and Pantry compose files.
- Shell syntax checks for infra scripts.
- `git diff --check`.

## Recommended Next Steps

1. Tune default rate-limit windows after observing real self-hosted usage.
2. Evaluate explicit non-root runtime users for production images.
3. Add broader authorization route-matrix coverage for household and platform-admin boundaries.
4. Continue with observability/support-tooling hardening without adding billing or hosted-only assumptions.
