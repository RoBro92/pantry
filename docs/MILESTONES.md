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

## Milestone 6: Shopping

- Shopping lists and list items.
- Basic consumption and replenishment workflows.

## Milestone 7: Hardening

- Test coverage expansion.
- Observability improvements.
- Security review and backup guidance.
- Self-hosted deployment refinement.

## Milestone 8: SaaS Readiness

- Hosted deployment topology.
- Plan-aware feature flags and usage counters.
- Private operational runbooks in `private-docs/`.
