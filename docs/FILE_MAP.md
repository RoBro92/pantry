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
- `apps/api/app/models/`: SQLAlchemy identity and tenancy models.
- `apps/api/app/api/routes/`: health, auth, admin, and household routes.
- `apps/api/app/api/deps/`: auth and tenancy dependencies.
- `apps/api/app/cli.py`: admin bootstrap and password reset commands.
- `apps/api/tests/`: focused API tests for auth and tenancy.

## Key Frontend Paths

- `apps/web/app/(auth)/login/page.tsx`: login page.
- `apps/web/app/(dashboard)/`: authenticated shell and platform admin pages.
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
