# Test Strategy

Run the smallest validation set that still covers the files you changed.

## Docs-Only Changes

For documentation or repo-layout changes, validation can stop at:

- checking links, paths, and command names against the repository
- running syntax checks for any changed shell scripts
- re-reading the changed docs for stale references or unsupported claims

## Application Changes

Use the local stack when behavior, runtime wiring, or user-visible flows changed:

```bash
docker compose up -d --build
docker compose run --rm api alembic upgrade head
```

Targeted checks:

```bash
npm run typecheck:web
npm run build:web
cd apps/api && pytest -q
./infra/scripts/smoke-check.sh
npm run test:e2e
```

Use the smallest relevant subset. E2E is only required when a covered user flow changed.

## Finish Cleanly

Shut the stack down when you are done:

```bash
docker compose down
```
