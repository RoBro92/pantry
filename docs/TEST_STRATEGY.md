# Test Strategy

This file is the concrete local validation policy for Pantry milestones. It defines the commands, ordering, and reporting expectations for local validation.

## Validation Principles

- Run the smallest relevant validation set that still exercises every changed area.
- Prefer unit and integration tests for logic changes.
- Use smoke checks to confirm changed services boot and respond correctly in the local stack.
- Run the Docker-backed Playwright suite when a user-facing flow changed and the covered paths overlap the shipped E2E scenarios.
- Do not mark a milestone complete without recording what was run, what passed, and what remains blocked.

## Local Validation Setup

Run these setup steps before milestone validation when needed:

```bash
cp .env.example .env
npm install
npx playwright install chromium
python3 -m pip install -r apps/api/requirements-dev.txt
```

If dependencies are already installed and `.env` already exists, reuse them.
Keep `.env` aligned with `.env.example` for service-to-service validation. In particular, the web smoke checks expect `INTERNAL_API_BASE_URL=http://api:8000`.
For host-side web validation commands, use `Node.js 20.x` with `npm 10.x`. Newer host runtimes may
fail in Next.js internals even when the Dockerized web service is healthy.

For docs-only or very small release/version scaffolding changes, proportionate validation may be limited to:

- `npm run version:show`
- the smallest relevant web command if package or runtime-version scripts changed
- targeted re-reading of generated or referenced docs/config files

## Validation Order

Use this order unless a narrower changed-area workflow is obviously sufficient:

1. Install or refresh dependencies needed for the changed area.
2. Start the local stack when service validation is required.
3. Run migrations and setup steps required by the change.
4. Run unit, integration, lint, and typecheck commands for the changed areas.
5. Run smoke checks for every changed service or feature surface.
6. Run E2E checks when user-facing flows changed and E2E coverage exists.
7. Shut the stack down after validation.
8. Record results in `docs/PROJECT_STATE.md`.

## Exact Local Commands

Start the stack in the background:

```bash
docker compose up -d --build
```

Run migrations explicitly when database-backed behavior changed or when validating a new migration:

```bash
docker compose run --rm api alembic upgrade head
```

Run API integration tests:

```bash
cd apps/api && pytest
```

Run current web validation commands:

```bash
npm run typecheck:web
npm run build:web
```

Seed deterministic E2E data in the running stack:

```bash
./infra/scripts/e2e-seed.sh
```

Run the current E2E suite:

```bash
npm run test:e2e
```

Run the repo smoke checks:

```bash
./infra/scripts/smoke-check.sh
```

Shut the stack down when validation is complete:

```bash
docker compose down
```

## When To Run Which Checks

### Unit and Integration Tests

Run focused tests first when the change affects:

- API business rules, auth, permissions, tenancy, or database behavior.
- Worker logic, job orchestration, or background side effects.
- Shared types or utility code with deterministic behavior.

For API work, `cd apps/api && pytest` is the current integration baseline and should run for any API or migration change.
Focused API suites such as `cd apps/api && pytest tests/test_recipe_api.py -q` should still run first when the changed domain has an isolated test module.

### Smoke Checks

Run smoke checks whenever the changed area touches a running service, route, page, session behavior, container startup, environment wiring, or local integration path.

Current expected smoke checks are:

- Web: load `/` and `/login` successfully.
- API: `GET /api/health` returns `status=ok`.
- Worker: `python -m worker.main --status` inside the running worker container returns `status=ok`.

`./infra/scripts/smoke-check.sh` performs the current baseline smoke checks against the local stack.

### E2E Checks

Run E2E when both conditions are true:

- A user-facing flow changed.
- The repository already contains E2E coverage for that flow.

Current Docker-backed Playwright coverage includes:

- First-run browser setup for the initial platform admin.
- Login and authenticated dashboard landing.
- Platform-admin user creation, household creation, and membership assignment.
- Platform admin diagnostics page load.
- Pantry create-location, add-stock, move-stock, and remove-stock flow.
- Recipe create/detail with pantry coverage display.
- Import upload, review, and confirm-to-pantry flow.
- AI unconfigured and unhealthy-provider UX.
- QR/location route auth redirect and post-login landing.

The current suite must remain deterministic:

- Seed data through `./infra/scripts/e2e-seed.sh`.
- Reset to an uninitialized install only through repo-owned helper scripts used by the suite.
- Run worker-dependent steps through the repo helper used by the tests.
- Do not depend on external AI, SMTP, or scraping services.

## Migration And Setup Notes

- Database schema changes require a matching migration strategy in the same change.
- Run migrations before smoke checks and before any validation that depends on the new schema.
- If validation needs bootstrap data, create it after migrations and before smoke or E2E checks.
- If a command auto-runs migrations on service startup, still run `alembic upgrade head` explicitly when validating schema changes so the migration path itself is exercised.

## Reporting In PROJECT_STATE.md

Every milestone-sized change should update `docs/PROJECT_STATE.md` with:

- A short summary of what changed.
- The exact validation commands run.
- Pass or fail status for each command.
- Any blockers, skipped checks, or missing coverage.
- The recommended next step.
