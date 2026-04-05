# Contributing

Keep contributions focused, reviewable, and aligned with the shipped self-hosted product.

## Local Setup

1. Copy `.env.example` to `.env`.
2. Start the stack with `docker compose up -d --build`.
3. Run migrations with `docker compose run --rm api alembic upgrade head`.
4. Open `http://localhost:3000/setup` on a fresh install.

For host-side web commands, use `Node.js 20.x` and `npm 10.x`.

## Expectations

- Keep changes scoped to the problem being solved
- Update public docs when install, update, runtime, or contributor workflows change
- Keep `apps/web`, `apps/api`, and `apps/worker` responsibilities clear
- Add or update tests when behavior changes
- Do not commit internal planning notes, private operational material, or local-only workspace files

## Validation

Run the smallest relevant validation set for the files you changed. Start with [docs/TEST_STRATEGY.md](/Users/robinbrown/Documents/GitHub/pantry/docs/TEST_STRATEGY.md).

Common commands:

```bash
npm run typecheck:web
npm run build:web
cd apps/api && pytest -q
./infra/scripts/smoke-check.sh
docker compose down
```
