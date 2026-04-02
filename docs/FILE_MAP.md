# File Map

## Root

- `VERSION`: canonical application version.
- `compose.yml`: local development stack.
- `.env.example`: environment variable template.
- `AGENTS.md`: primary durable Codex operating instructions for this repository.
- `README.md`: project overview and local setup.

## Applications

- `apps/web/`: Next.js frontend with login page, protected shell, and platform admin pages.
- `apps/api/`: FastAPI backend with SQLAlchemy models, Alembic migrations, auth routes, and CLI commands.
- `apps/worker/`: Python worker scaffold.

## Packages

- `packages/shared-types/`: shared TypeScript constants for deployment modes, roles, and domain entities.

## Infrastructure

- `infra/docker/`: Dockerfiles for web, API, and worker.
- `infra/scripts/`: small repository utility scripts such as version helpers and repeatable smoke checks.

## Key Backend Paths

- `apps/api/alembic/`: migration environment and migration history.
- `apps/api/app/models/`: SQLAlchemy identity, tenancy, pantry, recipe, stock-lot, and audit-event models.
- `apps/api/app/api/routes/`: health, auth, admin, and household routes.
- `apps/api/app/api/deps/`: auth and tenancy dependencies.
- `apps/api/app/api/routes/pantry.py`: household-scoped pantry routes for locations, products, stock lots, and pantry views.
- `apps/api/app/api/routes/recipes.py`: household-scoped recipe routes for list/detail, create/update, and URL import capture.
- `apps/api/app/cli.py`: admin bootstrap and password reset commands.
- `apps/api/app/services/pantry_*.py`: pantry catalog, stock mutation, normalization, and query services.
- `apps/api/app/services/recipe_*.py`: recipe create/update, deterministic matching, coverage, shopping-gap derivation, and URL import capture.
- `apps/api/tests/`: focused API tests for auth, tenancy, pantry, and recipe flows.

## Key Frontend Paths

- `apps/web/app/(auth)/login/page.tsx`: login page.
- `apps/web/app/(dashboard)/`: authenticated shell, pantry pages, and platform admin pages.
- `apps/web/app/(dashboard)/app/households/[householdExternalId]/page.tsx`: household pantry view with search, stock lots, near-expiry, and audit activity.
- `apps/web/app/(dashboard)/app/households/[householdExternalId]/recipes/`: recipe list, create, detail, and edit pages.
- `apps/web/components/pantry-controls.tsx`: pantry creation and add-stock controls.
- `apps/web/components/pantry-lot-actions.tsx`: inline remove and move stock actions.
- `apps/web/components/recipe-form.tsx`: client-side manual recipe create/edit form with ingredient rows and pantry-product links.
- `apps/web/lib/server-auth.ts`: server-side session and admin data fetching helpers.

## Documentation

- `docs/PROJECT_STATE.md`: latest implementation state, validation results, blockers, and next recommended step.
- `docs/MILESTONES.md`: roadmap.
- `docs/ARCHITECTURE.md`: high-level technical shape.
- `docs/DOMAIN_MODEL.md`: initial entity definitions.
- `docs/SECURITY.md`: security posture and guardrails.
- `docs/TEST_STRATEGY.md`: milestone validation policy, command order, and reporting expectations.
- `docs/CODEX_RULES.md`: concise repo-specific Codex guidance that defers to `AGENTS.md` and `docs/TEST_STRATEGY.md`.

## Local-Only

- `private-docs/`: gitignored space for SaaS operations or private runbooks.
