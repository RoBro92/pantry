# Project State

## Current Milestone

Pantry now has a staged first-run setup wizard and a dedicated login entry flow.

## What Changed

- Added backend setup staging with transactional finalisation
- Added polished web login and first-run wizard routing
- Added dietary preference persistence for households and users
- Added setup-specific API coverage and expanded E2E coverage
- Restored the public `docs/` set referenced by `AGENTS.md`

## Validation

- `cd apps/api && pytest -q tests/test_auth_api.py tests/test_setup_api.py`
- `cd apps/api && pytest -q`
- `./infra/scripts/smoke-check.sh`
- `npm run test:e2e`
- `docker compose exec -T web sh -lc 'export NEXT_PUBLIC_APP_VERSION=$(cat /workspace/VERSION) && npm run build --workspace @pantry/web'`

## Known Gaps

- The containerised Next.js production build completed compile, type-check, and static generation, then was killed while finishing build traces. The local dev stack was restarted and remained healthy after validation.

## Next Step

Open the local setup wizard in a browser, validate the first-run UX manually, and then decide whether to tune the production build memory footprint further.
