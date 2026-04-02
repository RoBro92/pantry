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

## Milestone 5: Shopping

- Shopping lists and list items.
- Basic consumption and replenishment workflows.

## Milestone 6: AI Integration

- LLM provider configuration.
- Ollama and OpenAI-compatible adapters.
- AI-assisted normalization and suggestion flows.
- Feature-gated AI entrypoints.

## Milestone 7: Hardening

- Test coverage expansion.
- Observability improvements.
- Security review and backup guidance.
- Self-hosted deployment refinement.

## Milestone 8: SaaS Readiness

- Hosted deployment topology.
- Plan-aware feature flags and usage counters.
- Private operational runbooks in `private-docs/`.
