# Project State

## Current Milestone

Pantry now has a product-centric pantry browser, attached Open Food Facts enrichment persistence, staged multi-room setup, and a clean shopping-list foundation.

## What Changed

- Expanded pantry product enrichment so Open Food Facts records persist as attached enrichment, not canonical product identity
- Added structured enrichment fields for ingredients, ingredient tokens, dietary tags, nutriments, and nutrition summary text alongside the existing UI summary
- Reworked the pantry page into a compact actions strip plus searchable product browser with expandable stock-lot detail
- Added manual ingredient tags, barcode scan hooks, and clearer duplicate-product routing in the add flow
- Added household shopping-list domain foundations and surfaced them in navigation
- Upgraded the setup wizard household step to stage multiple Rooms and storage locations with refresh-safe persistence
- Restyled recent activity into a compact pantry activity log

## Validation

- `cd apps/api && pytest -q tests/test_open_food_facts.py tests/test_pantry_api.py`
- `cd apps/api && pytest -q tests/test_setup_api.py`
- `cd apps/api && pytest -q tests/test_pantry_api.py::test_pantry_entry_detects_existing_product_then_adds_new_stock_lot tests/test_setup_api.py::test_setup_finalize_commits_all_staged_data_and_authenticates`

## Known Gaps

- Browser camera barcode scanning is implemented as a capability-checked foundation and still depends on secure-context browser support
- The shopping list is intentionally lightweight in this milestone and does not yet model full shopping trips, aisle ordering, or collaborative sync
- Local web type-check/build validation can still be slower than the API suite and may need a dedicated longer-running pass in some environments

## Next Step

Use the milestone map in [docs/MILESTONES.md](/Users/robinbrown/Documents/GitHub/pantry/docs/MILESTONES.md) to sequence the next passes: barcode hardening, richer depletion-to-shopping workflows, and deeper dietary/AI use of attached enrichment.
