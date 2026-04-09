# Contributing

Keep changes focused, reviewable, and aligned with the shipped self hosted product.

## Workflow

1. Start from an up to date branch.
2. Keep the change narrow and reviewable.
3. Run the smallest validation set that covers the files you changed.
4. Update public docs when install, runtime, safety, or contributor behavior changes.
5. Open a pull request for review instead of working directly on `main`.

Recommended branch prefixes:

- `feature/...`
- `fix/...`
- `docs/...`
- `release/...`

## Local Development Stack

Pantry provides a source-based helper for local branch work:

```bash
./infra/scripts/dev-stack.sh start fresh
./infra/scripts/dev-stack.sh start demo
```

- `fresh` resets the local environment to the first run setup flow
- `demo` resets the local environment and seeds stable demo data
- switch modes without a rebuild with `./infra/scripts/dev-stack.sh reset fresh` or `./infra/scripts/dev-stack.sh reset demo`
- stop the stack with `./infra/scripts/dev-stack.sh down`
- follow logs with `./infra/scripts/dev-stack.sh logs`
- rebuild images only when Dockerfiles or dependencies changed with `./infra/scripts/dev-stack.sh rebuild`
- the helper prefers `.env.local`, falls back to `.env`, and bootstraps `.env.local` from `.env.example` if needed
- web edits in `apps/web` and `packages/shared-types` hot reload in browser
- API edits in `apps/api/app` and Alembic files auto-reload the FastAPI process
- worker edits in `apps/worker/worker` and shared API-side worker dependencies restart the worker process automatically

Cross-platform note:
Docker Desktop file polling is enabled automatically by the helper on macOS and Windows-like shells. Linux keeps native file watching by default. If your host still misses changes, set `PANTRY_WEB_WATCHPACK_POLLING=true`, `PANTRY_API_WATCHFILES_FORCE_POLLING=true`, and `PANTRY_WORKER_WATCHFILES_FORCE_POLLING=true` before starting the stack.

Demo credentials:

- `demoadmin` / `demopass`
- `demouser` / `demopass`

## Expectations

- Keep `apps/web`, `apps/api`, and `apps/worker` responsibilities clear
- Add or update tests when user visible behavior changes
- Keep internal planning notes and local only material out of `docs/`
- diffs will be code reviewed before being merged

## Validation

Start with [docs/TEST_STRATEGY.md](TEST_STRATEGY.md).

Common commands:

```bash
npm run dev:stack:fresh
npm run dev:stack:demo
npm run dev:stack:down
npm run typecheck:web
npm run build:web
cd apps/api && pytest -q
./infra/scripts/smoke-check.sh
npm run test:e2e
```
