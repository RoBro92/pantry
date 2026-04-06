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
- Additional stack and E2E validation is expected for user-facing milestone completion

## Known Gaps

- Full stack validation should be rerun against the local Docker stack after any follow-up UI adjustments

## Next Step

Run the full local stack, execute the updated E2E suite, and verify the first-run wizard end to end in the browser.
