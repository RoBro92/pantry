# Full Repo Audit Summary

Date: 2026-05-05

## What Was Found

No confirmed critical issue was found. High-risk confirmed issues included recipe URL SSRF, unsafe restore/import storage path trust, broad frontend API proxying, login open redirect handling, weak production secret defaults, and static health checks that did not verify Postgres, Redis, or migrations.

Production risks included missing backup storage mounts, queue jobs that could remain stuck, Redis clients not being closed, and limited live-stack validation coverage. Remaining hosted-readiness gaps are rate limiting, session revocation, observability, abuse controls, and support tooling.

## What Was Fixed

- Recipe URL import now blocks private/local/reserved targets, validates redirects, caps redirects/body size, and requires HTML.
- Backup restore now validates staged IDs and import source storage paths.
- Import storage resolution now enforces safe relative paths under the configured root.
- Production startup now rejects weak or shared session/settings encryption secrets.
- `/api/ready` now checks database, migration head, and Redis readiness.
- Setup mutation endpoints close after initialization.
- Import jobs can be reclaimed after stale processing state; queue claims use row locking where supported.
- Redis runtime helpers close clients.
- Frontend API proxy now uses path/header allowlists and cross-origin mutation checks.
- Login redirect paths are restricted to safe app-internal paths.
- Household pages now perform route-level access checks.
- Production Compose/env/scripts now include backup storage, readiness checks, stronger container options, and `npm ci`.

## What Was Not Fixed

- Login/password reset rate limiting.
- Session revocation after password reset/change.
- API-wide CSRF policy for direct API deployments.
- Live PostgreSQL queue contention tests.
- Full Docker smoke/e2e validation.
- Dialog focus/accessibility regression tests.
- Hosted-style observability, quotas, abuse controls, and support tooling.

## Risk Remaining

The immediate high-risk self-hosted security issues are reduced, but authentication abuse controls and session revocation remain important before any hosted/SaaS exposure. Queue behavior is safer but not stress-tested against a live PostgreSQL multi-worker stack. Docker stack smoke/e2e could not be run because the local Docker daemon was unavailable.

## Recommended Next Steps

1. Add Redis-backed rate limiting for login and password reset.
2. Add session-version revocation for password reset/change.
3. Add a direct-API CSRF/origin policy appropriate for self-hosted deployments.
4. Run Docker demo stack, smoke checks, and Playwright e2e when Docker is available.
5. Add PostgreSQL concurrency tests for queue claiming.
