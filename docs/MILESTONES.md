# Milestones

## Milestone 0: Foundation

- Monorepo scaffold.
- Next.js web shell.
- FastAPI API shell with health endpoint.
- Python worker shell with status placeholder.
- Docker Compose local stack.
- Initial product, architecture, security, and operational docs.

Status: complete.

## Milestone 1: Identity And Household Core

- Users, households, memberships, and roles.
- Login and session auth.
- Admin bootstrap CLI.
- Password reset CLI.
- Initial admin shell pages in the web app.
- First database migrations and persistence model.

Status: foundation implemented.
Current scope delivered:

- Alembic migration and SQLAlchemy models for identity and tenancy foundations.
- Session-based auth endpoints with signed cookies.
- Initial authorization helpers and tenant membership resolution.
- Platform admin overview, user, and household pages.
- Focused API tests for auth and server-side household scoping.

## Milestone 2: Pantry Structure And Inventory

- Location groups and locations.
- Products, aliases, barcodes, and stock lots.
- Basic CRUD flows and stock adjustments.
- Audit event capture for key inventory mutations.

Status: foundation implemented.
Current scope delivered:

- Alembic migration and SQLAlchemy models for pantry location groups, locations, products, aliases, barcodes, stock lots, and audit events.
- Household-scoped pantry API routes for overview, near-expiry, pantry structure creation, stock add/remove/move, and audit activity.
- Next.js household pantry page with search/filtering, aggregate totals, lot actions, near-expiry visibility, and recent activity.
- Focused pantry API tests plus repo smoke validation for the local stack.

## Milestone 3: Recipe Core

- Manual recipe entry and editing.
- Recipe listing and detail views.
- Recipe ingredients with quantity, unit, notes, and pantry-product links.
- Pantry coverage checks and derived shopping gaps.
- URL recipe import capture foundation.
- Recipe audit-event coverage for create and update actions.

Status: foundation implemented.
Current scope delivered:

- Alembic migration and SQLAlchemy models for `Recipe`, `RecipeIngredient`, and `RecipeURLImport`.
- Household-scoped recipe API routes for list/detail, manual create/update, and URL import capture.
- Deterministic ingredient auto-matching plus pantry coverage and shopping-gap derivation from active stock lots.
- Next.js recipe list, create, edit, and detail pages connected to household pantry products.

## Milestone 4: Imports

- Import job lifecycle.
- Source-file storage and validation.
- Reviewable import lines.
- Safe parsing pipeline for hostile uploads.
- Reviewed confirm-to-pantry workflow.
- Worker-backed asynchronous import processing.

Status: foundation implemented.
Current scope delivered:

- Alembic migration and SQLAlchemy models for `ImportJob`, `ImportSourceFile`, and `ImportLine`.
- Safe upload storage outside web-served paths with application-level size/type validation and future scan-status hooks.
- Household-scoped import API routes for upload, inbox/history, detail, line review, ignore/update, and confirm-to-pantry flows.
- Worker-backed parsing for structured JSON, CSV, TSV, and plain-text imports with deterministic matching and observable lifecycle transitions.
- Next.js import inbox/history and import detail review pages with line editing, suggested matches, and explicit confirmation into pantry stock lots.

## Milestone 5: AI Provider Abstraction And Pantry-Aware Suggestions

- AI provider configuration model and service abstractions.
- Ollama and OpenAI-compatible provider adapters.
- Pantry-aware suggestion foundations that can plug into recipes and import review without hard-coding a single provider.
- Feature-gated entrypoints for future AI-assisted parsing and matching.

Status: foundation implemented.
Current scope delivered:

- Alembic migration and SQLAlchemy model for instance-scoped `AIProviderConfig`, with shape ready for future household overrides.
- Encrypted-at-rest provider secret handling plus provider health metadata, deployment-level AI feature gating, and adapter abstractions for Ollama and OpenAI-compatible APIs.
- Platform admin API and web foundation for saving provider configuration and running provider health checks.
- Household AI status and read-only suggestion APIs with structured pantry and recipe context assembly plus JSON output contracts.
- Household AI suggestions page with clear unavailable and unhealthy states and a minimal admin AI provider configuration page.

## Milestone 6: Platform Admin Diagnostics, SMTP, QR Links, And Admin Polish

- Platform admin diagnostics routes and UI.
- Honest instance health/reporting surfaces built from measurable app/runtime data only.
- Instance-level SMTP configuration foundation with encrypted secret storage and lightweight connectivity testing.
- Public/browser base URL setting for generated links.
- Pantry location QR generation and authenticated location deep-link flow.
- Admin console navigation cleanup for installation-level surfaces.

Status: foundation implemented.
Current scope delivered:

- Alembic migration and SQLAlchemy model for installation-scoped public/browser URL and SMTP foundation settings.
- Platform admin settings, SMTP, and diagnostics API routes with encrypted SMTP password storage, redacted responses, and lightweight SMTP connectivity testing.
- Redis-backed worker heartbeat publishing plus measured diagnostics coverage for API uptime, worker state, Redis reachability, queue counts, database health/size, entity counts, AI summary, SMTP summary, and public URL summary.
- Pantry location browser-link metadata in API responses plus an authenticated `/locations/{locationRoute}` browser route for QR deep links.
- Next.js admin layout and section navigation for overview, users, households, AI, SMTP, diagnostics, and settings pages.
- Inline server-rendered QR codes for pantry locations that rebuild from the current configured public/browser base URL.

## Milestone 7: SaaS-Readiness Pass

- Deployment-mode cleanup and first explicit feature-flag skeleton.
- Usage/quota counter skeleton.
- Demo-mode skeleton.
- First real E2E suite for core user-facing flows if it still does not exist.
- Additional self-hosted hardening where it directly supports later hosted expansion.

Status: implemented.
Current scope delivered:

- Docker-backed Playwright E2E coverage for login, diagnostics, pantry, recipe, import, AI state handling, and QR/location auth flows.
- Deterministic E2E seeding helpers plus worker-once helpers so browser tests do not depend on external services.
- Recipe URL imports now queue worker processing, parse lightweight structured metadata, create recipes, and surface explicit failure states.
- Import parsing now skips empty rows safely and flags invalid quantities or dates for review instead of failing unclearly.
- AI runtime failures now degrade cleanly for users while marking provider health unhealthy, and SMTP config validation now rejects malformed host inputs early.
- Internal prompt/Codex docs were removed from the public repo and retained only in local `private-docs/`.
- Deployment modes now resolve as `self_hosted`, `demo`, and `saas`, with server-side feature flags and usage counters in place but no SaaS product logic or UI.

## Milestone 8: Product Hardening, UX Polish, Setup Experience, And Release Readiness

- Improve first-run and setup experience for self-hosted installs.
- Add browser-based bootstrap for the initial platform admin.
- Improve platform-admin usability for creating households, users, and memberships.
- Harden validation, empty states, error handling, and release-readiness docs.
- Tighten permission boundaries and extend E2E coverage around setup and admin provisioning.

Status: implemented.
Current scope delivered:

- Browser-based `/setup` flow for the first platform admin, backed by one-time server-side enforcement.
- Installation-console user creation, household creation, and membership assignment flows.
- Role-aware pantry UX that hides structure-management actions from `household_user` while leaving stock handling available.
- Better empty states, validation messaging, import/review guidance, admin navigation cues, and version visibility.
- Expanded deterministic Playwright coverage for first-run setup and admin-managed provisioning.

## Milestone 9: Shopping And Daily Household Workflows

- Shopping lists and list items.
- Recipe-gap capture into shopping.
- Deliberate consumption and replenishment workflows that connect pantry state to day-to-day use.
- Clear household UX for what to buy, what was bought, and what should be consumed.

Status: planned.

## Milestone 10: UI, Accessibility, And Interaction Refinement

- Improve layout consistency, feedback states, readability, and interaction polish across pantry, imports, recipes, AI, and admin flows.
- Address usability friction that remains after the initial hardening pass.
- Improve mobile fit, empty-state clarity, and accessibility semantics without changing the core architecture.

Status: planned.

## Milestone 11: Release, Versioning, And Update Workflow

- Formalize `VERSION` as the release source of truth across web, API, worker, and published artifacts.
- Publish versioned container images to GitHub Container Registry.
- Publish GitHub Releases and use release metadata as the update source for self-hosted operators.
- Add admin-visible update-available foundations on top of current version display.
- Keep changelog mechanics lightweight until the product stabilizes further.

Status: planned.

## Milestone 12: Production Deployment And LXC Readiness

- Add production-oriented deployment guidance beyond local Compose.
- Define the recommended self-hosted production path for Docker on LXC-hosted infrastructure.
- Document persistent volumes, backups, reverse proxy/TLS, secret handling, and rollout/rollback expectations.
- Prepare the repository for pinned-image deployment from GHCR rather than local source builds.

Status: planned.

## Milestone 13: Final Self-Hosted Release Candidate

- Consolidate remaining self-hosted blockers after shopping, UX refinement, release workflow, and deployment work land.
- Close the highest-value polish, observability, backup, and upgrade gaps for a stable self-hosted release.
- Produce a clear release checklist for the first broader public self-hosted version.

Status: planned.

## Milestone 14: Private Hosted Boundary Preparation

- Create or align the private hosted-services repository only after the public self-hosted product is release-ready.
- Formalize which contracts, docs, and packages remain shared versus private.
- Keep the public repo self-hosted-first and free of hosted billing, support, or control-plane internals.

Status: planned.

## Milestone 15: SaaS Implementation

- Build hosted-only product logic only after the self-hosted release path is stable and the public/private boundary is clear.
- Hosted tenant lifecycle, billing, support tooling, and SaaS operations belong here rather than in earlier self-hosted milestones.

Status: planned.
