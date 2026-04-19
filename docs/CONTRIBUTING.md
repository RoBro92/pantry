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

Pantro provides a repo-root wrapper for local branch work:

```bash
./pantro start --fresh
./pantro start --demo
```

- `fresh` resets the local environment to the first run setup flow
- `demo` resets the local environment and seeds stable demo data
- each `./pantro start --fresh` or `./pantro start --demo` run replaces the full local web, api, and worker stack before seeding the selected mode
- switch modes without a rebuild with `./pantro reset --fresh` or `./pantro reset --demo`
- stop and remove the full local stack with `./pantro stop`
- follow logs with `./pantro logs`
- check the current stack with `./pantro status`
- rebuild images only when Dockerfiles or dependencies changed with `./pantro rebuild`
- the helper prefers `.env.local` when present, otherwise `.env`, and bootstraps `.env.local` from `.env.local.example` if needed
- optional `PANTRO_LOCAL_AI_*` and `PANTRO_LOCAL_SMTP_*` values in `.env.local` pre-populate fresh setup and local demo-mode AI/SMTP settings without committing secrets to the repo
- legacy `PANTRY_LOCAL_AI_*` and `PANTRY_LOCAL_SMTP_*` names are also supported for backward compatibility in the local source stack
- bootstrap validation runs once after demo seed or setup finalize; Pantro does not background-poll AI or SMTP health in local development
- web edits in `apps/web` and `packages/shared-types` hot reload in browser
- API edits in `apps/api/app` and Alembic files auto-reload the FastAPI process
- worker edits in `apps/worker/worker` and shared API-side worker dependencies restart the worker process automatically

Cross-platform note:
Docker Desktop file polling is enabled automatically by the helper on macOS and Windows-like shells. Linux keeps native file watching by default. If your host still misses changes, set `PANTRO_WEB_WATCHPACK_POLLING=true`, `PANTRO_API_WATCHFILES_FORCE_POLLING=true`, and `PANTRO_WORKER_WATCHFILES_FORCE_POLLING=true` before starting the stack. On Windows, run `./pantro` from Git Bash or WSL.

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
./pantro start --fresh
./pantro start --demo
./pantro stop
npm run typecheck:web
npm run build:web
cd apps/api && pytest -q
./infra/scripts/smoke-check.sh
npm run test:e2e
```
