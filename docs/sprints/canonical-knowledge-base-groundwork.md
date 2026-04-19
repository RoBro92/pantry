# Canonical Knowledge Base Groundwork

## Goal

Introduce the first local-only canonical ingredient and product knowledge-base foundation so Pantro can start linking household pantry products and recipe ingredient matching to explicit canonical identities without turning AI or Open Food Facts into canonical truth.

## In Scope Deliverables

- Add first-class local canonical tables for canonical items, aliases, and product links.
- Add deterministic canonical matching for manual add, product create/update, and barcode-backed product metadata.
- Allow unmatched products to create explicit pending local canonical proposals.
- Add canonical-aware recipe fallback matching when direct product and alias matching miss.
- Seed a small local canonical starter set for demo/bootstrap flows.
- Surface a small canonical link/proposal summary in pantry product responses and the product browser details panel.

## Out Of Scope

- Hosted or shared canonical sync.
- SaaS, billing, or community submission flows.
- Full recipe model rewrite.
- Replacing current AI product intelligence.
- Treating Open Food Facts or AI output as auto-verified canonical truth.

## Implementation Plan

- Add household-scoped canonical item, canonical alias, and product canonical link models plus migration.
- Add a canonical matching service that prefers verified local aliases first, pending aliases second, then creates a pending proposal.
- Re-run canonical matching when products are created, updated, enriched, or have manual add metadata merged.
- Use verified canonical aliases as a recipe fallback matcher only after direct product and product-alias lookup miss.
- Seed a small verified canonical starter set in demo mode to keep the feature from being empty infrastructure.

## Acceptance Criteria

- Canonical tables exist and migrate cleanly.
- Products can link to canonical items without breaking pantry flows.
- Manual add attempts deterministic canonical matching.
- Barcode-backed product creation can link to a verified canonical item.
- Unmatched products create pending local canonical proposals instead of forced truth.
- Recipe fallback can resolve via verified canonical linkage.
- Open Food Facts and AI remain advisory inputs and do not auto-promote canonical truth.

## Files Expected To Change

- `apps/api/alembic/versions/20260419_000021_canonical_knowledge_base_groundwork.py`
- `apps/api/app/models/canonical_item.py`
- `apps/api/app/models/canonical_alias.py`
- `apps/api/app/models/product_canonical_link.py`
- `apps/api/app/models/product.py`
- `apps/api/app/models/household.py`
- `apps/api/app/models/__init__.py`
- `apps/api/app/services/canonical_knowledge.py`
- `apps/api/app/services/pantry_catalog.py`
- `apps/api/app/services/pantry_stock.py`
- `apps/api/app/services/product_enrichment.py`
- `apps/api/app/services/pantry_queries.py`
- `apps/api/app/services/recipe_matching.py`
- `apps/api/app/services/development_seed.py`
- `apps/api/app/schemas/pantry.py`
- `apps/api/tests/test_pantry_api.py`
- `apps/api/tests/test_recipe_api.py`
- `apps/api/tests/test_platform_admin_api.py`
- `apps/web/lib/api-types.ts`
- `apps/web/components/pantry-product-browser.tsx`

## AI And Enrichment Compatibility

Canonical truth stays explicit and reviewable. Open Food Facts enrichment can supply advisory product names and barcodes that help a product link to an already verified local canonical alias, but OFF data does not create verified canonical truth by itself. AI product intelligence remains separate, rerunnable, and non-canonical.

## Verification Pass

- Added focused API coverage for verified canonical alias matching on pantry add.
- Added focused API coverage for pending canonical proposal creation on unmatched pantry add.
- Added focused API coverage for relinking after product rename.
- Added focused API coverage for verified barcode canonical linkage.
- Added focused API coverage proving OFF enrichment alone does not auto-verify canonical truth.
- Added focused recipe coverage for canonical fallback matching after direct name and product-alias lookup miss.
- Added an explicit admin settings test confirming that `PUBLIC_BROWSER_BASE_URL` environment precedence overrides the saved database value.

## Practical Local Bootstrap Pass

- Expanded the starter canonical seed with a verified `Mayonnaise` cluster so common local/demo variants like `mayo` and `Tesco Mayonnaise` resolve deterministically.
- Added a household relink/backfill pass so existing products can be re-synced against the seeded canonical set instead of staying stranded on older pending proposals.
- Added create-time duplicate prevention that checks verified canonical matches before creating a new pantry product. When a verified canonical equivalent already maps to an existing household product, Pantro now routes the add flow back to that product instead of creating a fresh pending duplicate.
- Kept unmatched items unchanged: they still create explicit pending local canonical proposals for later review.
- Kept future hosted/shared knowledge-base work out of scope. This pass only improves local bootstrap usefulness and household-level dedupe.

## Final Practical Usage Fixes

- Extended the mayonnaise starter cluster and canonical name matching so `Tesco mayo` resolves to the same verified local canonical identity as `Mayonnaise`, `mayo`, and `Tesco Mayonnaise`.
- Simplified duplicate handling in the current add flows so reusing the existing product stays the default path and any separate-product override is pushed behind a smaller secondary disclosure.
- Clarified canonical proposal copy in the product details view so pending proposals read as local, reviewable suggestions rather than verified truth.
- Diagnosed and fixed the local dev bootstrap issue in `infra/scripts/dev-stack.sh`: `.env.local` is now the preferred local source file, and the helper no longer exports empty local AI/SMTP variables that override env-file values inside Docker Compose.

## Public Base URL Override Status

Current diagnosis: intended config precedence, not a canonical-layer bug. When `PUBLIC_BROWSER_BASE_URL` is set in the runtime environment, the saved database override persists but the effective live value remains the environment override. The existing admin UI reflects the API response, so this does not currently look like a stale-client bug.
