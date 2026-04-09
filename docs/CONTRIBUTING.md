# Contributing

Keep changes focused, reviewable, and aligned with the shipped self-hosted product.

## Workflow

1. Start from an up-to-date branch.
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

- `fresh` resets the local environment to the first-run setup flow
- `demo` resets the local environment and seeds stable demo data
- stop the stack with `./infra/scripts/dev-stack.sh down`
- follow logs with `./infra/scripts/dev-stack.sh logs`

Demo credentials:

- `demoadmin` / `demopass`
- `demouser` / `demopass`

## Expectations

- Keep `apps/web`, `apps/api`, and `apps/worker` responsibilities clear
- Add or update tests when user-visible behavior changes
- Keep internal planning notes and local-only material out of `docs/`
- Keep `private-docs/` local-only and untracked
- Review generated diffs before merging

## Validation

Start with [docs/TEST_STRATEGY.md](TEST_STRATEGY.md).

Common commands:

```bash
npm run typecheck:web
npm run build:web
cd apps/api && pytest -q
./infra/scripts/smoke-check.sh
npm run test:e2e
```
