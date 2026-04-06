# Contributing

Keep changes focused, reviewable, and aligned with the shipped self-hosted product.

## Local Setup

1. Copy `.env.example` to `.env`.
2. Start the stack with `docker compose up -d --build`.
3. Run migrations with `docker compose run --rm api alembic upgrade head`.
4. Open `http://localhost:3000/`.

Fresh installs should land in the first-run setup wizard. Completed installs should land on the login page.

## Expectations

- Keep `apps/web`, `apps/api`, and `apps/worker` responsibilities clear
- Update public docs when runtime, install, or contributor workflows change
- Add or update tests when user-visible behavior changes
- Do not commit internal-only planning notes or local workspace files

## Validation

Start with [docs/TEST_STRATEGY.md](/Users/robinbrown/Documents/GitHub/pantry/docs/TEST_STRATEGY.md).

Common commands:

```bash
npm run typecheck:web
npm run build:web
cd apps/api && pytest -q
./infra/scripts/smoke-check.sh
docker compose down
```
