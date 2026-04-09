# Test Strategy

Run the smallest validation set that still covers the files you changed.

## Documentation Changes

For docs-only work, validation can stop at:

- checking links and paths
- checking command names against the repository
- re-reading the changed docs for stale or unsupported claims

## Application Changes

Use the local stack when runtime wiring or user-visible flows changed:

```bash
docker compose up -d --build
docker compose run --rm api alembic upgrade head
```

Common checks:

```bash
npm run typecheck:web
npm run build:web
cd apps/api && pytest -q
./infra/scripts/smoke-check.sh
npm run test:e2e
```

Use the smallest relevant subset. End-to-end coverage is most useful when a covered browser flow changed.

## Finish Cleanly

Shut the stack down when you are done:

```bash
docker compose down
```
