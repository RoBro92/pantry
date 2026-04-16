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
./pantry start --fresh
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

## Release Gate

Smoke validation and Playwright E2E are not currently enforced on every pull request. They are enforced in the release validation gate through `./infra/scripts/validate-release.sh` and the tag-triggered `Release Publish` workflow.

The mandatory pre-release gate is:

```bash
./infra/scripts/validate-release.sh
```

That gate now boots the local demo stack, runs `./infra/scripts/smoke-check.sh`, runs `npm run test:e2e`, and then continues with the existing release-oriented checks.

When iterating locally before the full gate, use:

```bash
./pantry start --demo
./infra/scripts/smoke-check.sh
npm run test:e2e
./pantry stop
```

## Finish Cleanly

Shut the stack down when you are done:

```bash
./pantry stop
```
