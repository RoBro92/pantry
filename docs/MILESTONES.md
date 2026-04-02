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

Status: next recommended milestone.

## Milestone 3: Imports

- Import job lifecycle.
- Source-file storage and validation.
- Reviewable import lines.
- Safe parsing pipeline for hostile uploads.

## Milestone 4: Recipes And Shopping

- Recipes and recipe ingredients.
- Shopping lists and list items.
- Basic consumption and replenishment workflows.

## Milestone 5: AI Integration

- LLM provider configuration.
- Ollama and OpenAI-compatible adapters.
- AI-assisted normalization and suggestion flows.
- Feature-gated AI entrypoints.

## Milestone 6: Hardening

- Test coverage expansion.
- Observability improvements.
- Security review and backup guidance.
- Self-hosted deployment refinement.

## Milestone 7: SaaS Readiness

- Hosted deployment topology.
- Plan-aware feature flags and usage counters.
- Private operational runbooks in `private-docs/`.
