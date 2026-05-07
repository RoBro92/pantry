# Mobile Household Shell Sprint

## Goal

Deliver the first focused mobile-first household UX sprint so Pantro is easier to use daily on a phone without changing the deployment model, starting SaaS work, or rewriting the underlying pantry schema.

## In-scope deliverables

- replace the always-on desktop household sidebar with a mobile-appropriate household navigation pattern while preserving desktop navigation
- improve the household pantry landing experience for narrow screens
- add a responsive card/list presentation for pantry inventory on small screens while keeping the desktop table available
- split household add-item entry into clearer scan-first and manual paths
- reduce stacked modal pressure for common pantry tasks on phones
- move enrichment and AI-heavy detail behind secondary disclosure in consumer pantry flows
- add or update the smallest relevant test coverage for the changed household pantry flows

## Out-of-scope items

- SaaS, billing, quotas, or hosted-only workflow changes
- native mobile app work
- release/version changes
- canonical ingredient schema or broader pantry model rewrites
- major admin/operator IA changes beyond shared shell separation already needed for household UX
- full design system rewrite or broad visual rebrand

## Implementation plan

1. Update the shared household shell to support a mobile header and bottom navigation while keeping the existing desktop sidebar.
2. Rework pantry controls into clearer household quick actions with separate scan-first and manual add entry points.
3. Add a small-screen pantry card/list view with thumb-friendly primary actions and progressive disclosure for details.
4. Simplify mobile add-item entry by supporting lighter scan-first and manual entry surfaces without changing backend endpoints.
5. Move enrichment and AI detail into secondary sections in the pantry browser so consumer-facing information stays primary.
6. Update relevant CSS and e2e coverage, then run web validation.

## Acceptance criteria

- phone-sized household navigation is usable without depending on a persistent desktop sidebar
- pantry inventory is easy to browse on a narrow viewport with item name, quantity, location, state, and primary actions visible
- users can start a scan-first flow separately from a manual add flow
- common pantry actions are available on mobile without heavy stacked modal reliance
- enrichment or debug-style detail is no longer the primary focus in household pantry views
- desktop household behaviour remains intact

## Files expected to change

- `docs/sprints/mobile-household-shell.md`
- `apps/web/components/app-shell.tsx`
- `apps/web/components/pantry-controls.tsx`
- `apps/web/components/pantry-product-browser.tsx`
- `apps/web/components/pantry-add-entry-dialog.tsx`
- `apps/web/components/barcode-scanner-dialog.tsx`
- `apps/web/app/(dashboard)/app/households/[householdExternalId]/page.tsx`
- `apps/web/app/globals.css`
- `tests/e2e/core-flows.spec.ts`

## Blocker Fix Pass

### Blocker summary

- replace the oversized mobile menu tile with a compact account-and-utility header
- keep dashboard, settings, admin, logout, and secondary household access reachable on mobile
- fix household bottom-nav active state so inventory does not stay highlighted across other sections
- correct mobile popup and stock-lot modal sizing, centring, and scroll behaviour
- reduce mobile pantry card height and action clutter while preserving key at-a-glance stock context
- harden narrow and landscape layouts for long text, stock-lot detail, and date fields

### Implementation adjustments

- move mobile utility navigation into a compact menu in the shared app shell and keep the bottom bar focused on household task areas
- align household-route detection with the actual current route instead of falling back to the first membership
- route the "what changed" popup through the shared modal shell and tighten modal viewport sizing and body scroll locking
- make stock-lot dialogs use the same mobile-safe modal sizing and show units in quantity flows
- condense pantry mobile cards, move secondary actions behind a light "More" treatment, and slim expanded detail on phones
- add wrap-safe text handling for long room and location names and collapse mobile date grids to single-column layouts
- extend the mobile breakpoint treatment to short landscape phone viewports

### Acceptance criteria for this pass

- no large duplicate mobile menu card remains on household screens
- mobile users can reach dashboard, settings, admin, logout, and remaining household routes without relying on the bottom bar
- bottom-nav active state only reflects the current household section
- the release-notes popup fits within the mobile viewport without horizontal scrolling
- stock-lot dialogs open in-place on mobile, fit their content more cleanly, and show units in quantity flows
- pantry cards are materially denser by default on mobile while keeping name, quantity, location, and state visible
- long room and location names wrap without overlapping or breaking card layout
- manual-add and stock-lot date fields fit narrow mobile layouts
- landscape phone pantry views keep the mobile shell and card list usable

### Files changed in blocker pass

- `docs/sprints/mobile-household-shell.md`
- `apps/web/components/app-shell.tsx`
- `apps/web/components/logout-button.tsx`
- `apps/web/components/modal-shell.tsx`
- `apps/web/components/admin-release-notes-dialog.tsx`
- `apps/web/components/pantry-product-browser.tsx`
- `apps/web/components/pantry-lot-actions.tsx`
- `apps/web/components/stock-lot-editor-dialog.tsx`
- `apps/web/components/stock-lot-adjust-dialog.tsx`
- `apps/web/components/stock-lot-move-dialog.tsx`
- `apps/web/components/stock-lot-delete-dialog.tsx`
- `apps/web/app/globals.css`
- `tests/e2e/core-flows.spec.ts`

## Final Pre-PR Fix Pass

### Issues addressed

- keep the compact mobile menu tile, but make the menu a real overlay instead of expanding the header block
- shorten bottom-nav labels so household navigation fits cleanly on phone screens
- fix stock-lot action layout and restore visible, usable stock-lot modals on both mobile and desktop
- add bulk scan to the compact add-product surface, remove barcode entry from manual add, and default scan-first OFF enrichment to apply when found
- tighten dashboard and pantry mobile density without starting a broader redesign

### Implementation decisions

- keep the mobile header compact and anchor the menu as an overlay with a dismiss scrim instead of growing the tile
- keep full household labels for accessibility while rendering shorter bottom-nav labels visually
- remove the mobile full-screen stock-lot modal override and keep stock-lot actions in a stable row with labeled buttons
- use the existing bulk-scan dialog as the extra add entry point instead of introducing a new workflow
- auto-select the first OFF candidate for barcode-led lookups and show an explicit ready-to-apply success message while still leaving the preview reviewable
- replace the mobile pantry `More` disclosure with a stable compact action grid and a lighter metadata block

### Acceptance criteria

- the mobile menu opens as an overlay from the compact header without creating blank tile space
- bottom-nav labels fit cleanly on mobile while active state remains correct
- stock-lot action controls stay readable and their modals visibly render on mobile and desktop
- bulk scan is reachable from the add-new-product surface
- manual add no longer exposes barcode input
- scan-first optional details no longer repeat barcode or OFF controls
- barcode-led OFF matches auto-apply by default and show a visible success state
- mobile dashboard and pantry views are denser without materially breaking desktop behaviour

### Files changed

- `docs/sprints/mobile-household-shell.md`
- `apps/web/app/(dashboard)/app/page.tsx`
- `apps/web/components/app-shell.tsx`
- `apps/web/components/pantry-controls.tsx`
- `apps/web/components/pantry-add-entry-dialog.tsx`
- `apps/web/components/pantry-product-browser.tsx`
- `apps/web/app/globals.css`
- `tests/e2e/core-flows.spec.ts`

## Final Modal Visibility Fix

### Root cause

- stock-lot dialogs were still rendered inline inside the pantry detail tree instead of through a top-level portal
- those inline dialogs sat under shell and panel ancestors that create their own visual context, so the backdrop appeared while the dialog surface itself could be clipped or trapped outside the visible viewport

### Files changed

- `docs/sprints/mobile-household-shell.md`
- `apps/web/components/modal-shell.tsx`
- `tests/e2e/core-flows.spec.ts`

### Acceptance criteria

- stock-lot adjust, edit, move, and delete actions open visible dialogs on desktop
- the same actions open visible dialogs on mobile
- the overlay and dialog stack correctly above the pantry detail tree
- the shared modal shell mounts outside ancestor clipping contexts so stock-lot dialogs are not hidden

## Mobile Usability And PWA Cleanup Pass

### Issues addressed

- remove build/version chrome and generic welcome copy from the daily mobile household header
- render the mobile inventory card list from the first server/client pass instead of waiting for a viewport effect
- prevent scan/manual add flows from opening before a household has a storage location, with a mobile admin path back to room management
- keep pantry filter controls in sync with URL-backed server results
- move activity and storage QR tools behind a secondary disclosure and remove raw audit action codes or full QR URLs from the main pantry path
- add manifest, mobile metadata, icon placeholders, and safe-area spacing for installable mobile use
- extend the instance AI setting schema and web setup/admin forms with OpenRouter and LiteLLM proxy options as OpenAI-compatible, operator-managed endpoints

### Acceptance criteria

- phone inventory remains visible without relying on a `matchMedia` hydration swap
- mobile add actions do not lead to an unsaveable required-location form
- daily household screens no longer show version/build text, raw audit action identifiers, full QR URLs, or AI provider/schema metadata in consumer disclosures
- Pantro exposes a valid web app manifest and theme/icon metadata without adding service-worker caching
- OpenRouter and LiteLLM proxy configuration can be saved and health-checked without adding billing, hosted control-plane, or native app work
