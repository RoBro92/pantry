# Test Strategy

Run the smallest validation set that still covers the files you changed.

## Documentation Changes

For docs only work, validation can stop at:

- checking links and paths
- checking command names against the repository
- re-reading the changed docs for stale or unsupported claims

## Application Changes

Use the local stack when runtime wiring or user-visible flows changed:

```bash
./pantro start --fresh
```

Common checks:

```bash
npm run typecheck:web
npm run build:web
cd apps/api && pytest -q
./infra/scripts/smoke-check.sh
npm run test:e2e
```

Use the smallest relevant subset for normal changes. End-to-end coverage is most useful when a covered browser flow changed.

## Local Smoke and E2E Prerequisites

Smoke and Playwright E2E run against the local Docker source stack only. They do not require hosted or SaaS infrastructure.

Prerequisites:

- Docker Engine with the Compose plugin available
- Node.js 20.x and npm 10.x
- `npm install` or `npm ci` already completed
- Playwright browsers installed with `npx playwright install`
- the local stack running in `fresh` or `demo` mode

Use the demo stack for normal full-flow validation:

```bash
./pantro start --demo
./infra/scripts/smoke-check.sh
CI=1 npm run test:e2e
./pantro stop
```

`./infra/scripts/smoke-check.sh` checks the web routes, the web API proxy, direct API readiness, database migration head, Redis, and worker status. Override `WEB_URL`, `API_URL`, or `COMPOSE_CMD` only when the stack is bound somewhere other than the defaults.

## Release Gate

Smoke validation and Playwright E2E are not currently enforced on every pull request. They are enforced in the release validation gate through `./infra/scripts/validate-release.sh` and the tag-triggered `Release Publish` workflow.

The mandatory pre-release gate is:

```bash
./infra/scripts/validate-release.sh
```

That gate now boots the local demo stack, runs `./infra/scripts/smoke-check.sh`, runs `CI=1 npm run test:e2e`, and then continues with the existing release-oriented checks.

When iterating locally before the full gate, use:

```bash
./pantro start --demo
./infra/scripts/smoke-check.sh
CI=1 npm run test:e2e
./pantro stop
```

## Finish Cleanly

Shut the stack down when you are done:

```bash
./pantro stop
```
