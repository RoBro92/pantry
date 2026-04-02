# Project State

Updated: 2026-04-02

## What Exists

- Root monorepo scaffold with `apps/`, `packages/`, `infra/`, `docs/`, and `private-docs/`.
- `VERSION` set to `0.1.0` as the intended source of truth for release versioning.
- Docker Compose stack for web, API, worker, PostgreSQL, and Redis.
- Next.js web app with a login page, authenticated app shell, and initial platform admin pages.
- FastAPI app with health endpoint, auth/session endpoints, platform admin endpoints, and tenant-aware household access checks.
- Minimal Python worker with config scaffold, structured logging, and placeholder status output.
- Shared TypeScript package with deployment modes, roles, and domain-entity constants.
- SQLAlchemy models plus an Alembic migration for `Role`, `User`, `Household`, and `Membership`.
- Password hashing via Argon2 and signed cookie sessions for the web login foundation.
- CLI commands for first-platform-admin bootstrap and password reset.
- API tests covering login/session behavior, email normalization, and tenant membership enforcement.
- Updated documentation covering product direction, architecture, security, tenancy, deployment, testing, and contribution rules.
- Durable Codex operating instructions centered on `AGENTS.md`, with milestone validation policy in `docs/TEST_STRATEGY.md`.
- A repeatable local smoke-check helper at `infra/scripts/smoke-check.sh` for web, API, and worker baseline validation.

## Assumptions In This Pass

- Self-hosted local development is the primary near-term target.
- Docker Compose is the quickest path to a consistent developer environment.
- PostgreSQL is the system of record; Redis supports worker and transient coordination concerns.
- Signed cookie sessions are sufficient for the current self-hosted foundation and can be replaced later if revocation or multi-device controls need stronger guarantees.
- The current admin web surface is intentionally read-oriented; richer create/update flows can follow once Milestone 2 and beyond firm up operational patterns.
- Private SaaS and operations material will live only in local `private-docs/`.

## Validation Workflow

- `AGENTS.md` is now the durable instruction source for future Codex milestone work.
- `docs/TEST_STRATEGY.md` defines the required local validation order and exact commands.
- Milestone work is not considered complete without recorded validation results, blockers, and next steps here.
- Docker-backed smoke validation should start the stack when needed and shut it down afterward.

## Latest Change

- Tightened repo-level Codex instructions so future milestone prompts can stay short and defer to `AGENTS.md`.
- Added a concrete validation policy covering setup, migrations, lint/type/test commands, smoke checks, E2E expectations, shutdown, and reporting.
- Added `infra/scripts/smoke-check.sh` to make baseline local service smoke validation repeatable.
- Wired `INTERNAL_API_BASE_URL` directly into the `web` service in `compose.yml` with a Docker-safe default of `http://api:8000`, so the running web container can always reach the API during smoke checks unless operators intentionally override it.
- Updated deployment and smoke-check guidance to reflect the Compose-level default and to point failed wiring checks at container recreation rather than only `.env` editing.

## Validation Results

- `bash -n infra/scripts/smoke-check.sh`: passed.
- `npm run typecheck:web`: passed.
- `npm run build:web`: passed.
- `docker compose up -d --build`: passed.
- `docker compose run --rm api alembic upgrade head`: passed.
- `docker compose exec -T web sh -lc 'printf %s "$INTERNAL_API_BASE_URL"'`: passed (`http://api:8000`).
- `./infra/scripts/smoke-check.sh`: passed.
- `docker compose down`: passed.

## Blockers / Gaps

- No dedicated E2E suite exists yet, so user-facing changes currently rely on targeted smoke checks plus service-specific tests.

## Recommended Next Milestone

Milestone 2 should implement:

- Location groups and locations
- Products, aliases, and stock lots
- Add, remove, and move stock flows
- Aggregated household inventory views
- Audit-event writes for inventory mutations

## Useful Commands

```bash
docker compose up -d --build
docker compose run --rm api alembic upgrade head
./infra/scripts/smoke-check.sh
docker compose down
docker compose run --rm api python -m app.cli bootstrap-platform-admin --email admin@example.com
docker compose run --rm api python -m app.cli reset-password --email admin@example.com
python3 -m pip install -r apps/api/requirements-dev.txt
cd apps/api && pytest
npm run typecheck:web
npm run build:web
```
