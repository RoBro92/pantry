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
