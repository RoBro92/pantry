# Milestones

## Current Delivery Slice

This milestone establishes the pantry product and UX foundations that later automation can safely build on:

- Open Food Facts is stored as attached Pantry product enrichment, not as the product record itself
- The pantry page is product-centric, searchable, and expandable instead of long-form stacked
- Setup can stage multiple Rooms and storage locations before finalization
- Shopping-list and depletion foundations exist without turning Pantry into a hosted or speculative workflow product

## Follow-On Milestones

### 1. Barcode And Capture Hardening

- improve browser-camera barcode coverage and device messaging
- add clearer scanner-first mobile affordances where capability checks pass
- expand validation and UX around barcode collisions and manual fallback

### 2. Depletion And Shopping Workflow Expansion

- turn depleted products and low-stock signals into more deliberate shopping-list suggestions
- support better review, clearing, and replenishment loops on the shopping list
- decide how recipe gaps and pantry depletion should hand off into shopping work

### 3. Enrichment-Aware Dietary And AI Context

- apply ingredient tokens, dietary tags, allergens, and nutriments in filtering and assistant context
- improve ingredient reasoning across manual tags plus external enrichment
- add richer policy around when enrichment should refresh or be re-linked

### 4. Pantry Operations Polish

- extend product and lot actions for faster stock adjustments on mobile
- refine table/list density and filter shortcuts from real usage
- continue tightening import, recipe, and pantry handoff points

## Deferred In This Milestone

- no hosted sync or SaaS-style shopping features
- no local image caching for Open Food Facts assets
- no automatic overwrite of Pantry product identity from external enrichment
- no fully built mobile scanning workflow beyond graceful browser support hooks
