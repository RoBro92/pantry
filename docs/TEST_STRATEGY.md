# Test Strategy

Run the smallest validation set that still covers the changed surface area.

For normal code changes, run validation from a branch before opening or merging a pull request.

## Application Changes

Use the local stack when user-visible routing, setup, or runtime wiring changed:

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

Pull requests should at minimum stay green on the repository validation workflow:

- `API Tests`
- `Web Checks`
- `Repo Sanity`

## Setup And Login Changes

When first-run or authentication UX changes, include:

- API tests for setup state and final completion
- E2E coverage for incomplete-setup redirect, wizard progression, refresh persistence, completion, and post-completion login flow

## Finish Cleanly

```bash
docker compose down
```
