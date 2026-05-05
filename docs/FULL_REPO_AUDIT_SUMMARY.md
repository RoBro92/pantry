# Full Repo Audit Summary

Date: 2026-05-05

## What Was Found

No confirmed critical issue was found. The original high-risk confirmed issues included recipe URL SSRF, unsafe restore/import storage path trust, broad frontend API proxying, login open redirect handling, weak production secret defaults, and static health checks that did not verify Postgres, Redis, or migrations.

The follow-up review focused on the remaining security and production-readiness gaps: auth abuse throttling, session revocation, direct API CSRF/origin protection, queue contention coverage, Docker smoke/e2e readiness, and modal focus regressions.

## What Was Fixed

- Redis-backed rate limiting now protects login, password reset request, and first-run setup mutation routes, with non-enumerating errors and an in-process fallback if Redis is unavailable.
- Password reset, password change, and email change now rotate `users.session_version`; old signed-cookie sessions are rejected and refreshed sessions continue to work.
- Unsafe direct API methods now require an allowed `Origin` or `Referer`; `WEB_APP_URL`, `API_BASE_URL`, and `CSRF_TRUSTED_ORIGINS` define the allowed self-hosted origins.
- PostgreSQL queue contention tests were added, including static `FOR UPDATE SKIP LOCKED` checks and gated live multi-worker/stale-reclaim tests behind `PANTRY_TEST_POSTGRES_URL`.
- Docker smoke/e2e helper scripts now perform clearer preflight/readiness checks for web, API, migration head, Redis, Postgres, and worker status where practical.
- Shared modal dialogs now move focus into the dialog, trap Tab, close on Escape, restore focus on close, and have Playwright regression coverage.
- The earlier pass also fixed SSRF, restore path trust, production secret validation, `/api/ready`, web proxy/header hardening, login redirect validation, setup closure, stale queue reclaiming, Redis client closure, and production Compose/env hardening.

## What Was Not Fixed

- Explicit non-root container users, broader observability, quotas, abuse controls, and hosted-style support tooling remain future work.

## What Could Not Be Tested

- Live Docker stack smoke/e2e validation was not completed because the Docker daemon was unavailable locally.
- Live PostgreSQL queue contention execution was not completed because `PANTRY_TEST_POSTGRES_URL` was not provided; deterministic static checks passed and live tests are ready to run.
- Playwright dialog assertions were not completed because the suite depends on Docker-backed e2e seeding in this repo.

## Risk Remaining

The highest-risk self-hosted security gaps found in the audit are now reduced. Remaining risk is mostly validation and operational maturity: Docker smoke/e2e still needs to be run on a machine with Docker, live queue contention needs a disposable PostgreSQL test database, and direct API automation must send an allowed `Origin`/`Referer` or be intentionally configured.

Redis-backed rate limiting falls back to per-process in-memory limits if Redis is unavailable, which preserves throttling but is weaker than shared Redis limits in a horizontally scaled deployment.

## Tests Run

- `pytest -q` in `apps/api` (`220 passed, 6 skipped`).
- Targeted backend auth/security/queue tests, including rate limits, session revocation, CSRF, and queue SQL checks.
- `node --test apps/web/lib/security-helpers.test.mjs`.
- `npm run typecheck:web` and `npm run build:web`.
- `npx playwright test tests/e2e/dialog-accessibility.spec.ts --list` discovered the dialog specs.
- Alembic head and SQLite migration upgrade checks.
- Docker Compose config validation for Pantro and Pantry compose files.
- Shell syntax checks for infra scripts.
- `git diff --check`.

## Recommended Next Steps

1. On a Docker-capable machine, run `./pantro start --demo`, `./infra/scripts/smoke-check.sh`, `CI=1 npm run test:e2e`, then `./pantro stop`.
2. Run `PANTRY_TEST_POSTGRES_URL=<postgres-url> pytest tests/test_queue_concurrency.py -q -rs` against a disposable PostgreSQL database.
3. Tune default rate-limit windows after observing real self-hosted usage.
4. Evaluate explicit non-root runtime users for production images.
5. Continue with observability/support-tooling hardening without adding billing or hosted-only assumptions.
