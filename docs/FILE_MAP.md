# File Map

Quick reference for the public repository layout.

## Product Code

- `apps/web/`: Next.js frontend
- `apps/api/`: FastAPI backend, Alembic migrations, and API test suite
- `apps/worker/`: background worker
- `packages/shared-types/`: shared TypeScript types and constants

## Deployment And Release Files

- `compose.yml`: local source-based development stack
- `compose.dev.yml`: local development overrides
- `infra/compose/pantry.yml`: released self-hosted stack
- `infra/env/pantry.env.example`: released environment template
- `infra/docker/`: Dockerfiles for local and released images
- `infra/scripts/`: install, update, health check, smoke check, release, and local helper scripts
- `.github/workflows/`: pull request validation and release publishing workflows

## Public Documentation

- `README.md`: product overview, install entry point, and docs index
- `AGENTS.md`: public repository working rules
- `docs/ARCHITECTURE.md`: high-level service and deployment layout
- `docs/CONTRIBUTING.md`: contributor workflow and local development commands
- `docs/DEPLOYMENT.md`: self-hosted install and update guidance
- `docs/SECURITY.md`: safe operation and data-handling notes
- `docs/TEST_STRATEGY.md`: proportionate validation guidance
- `docs/VERSIONING.md`: release and update model

## Local-Only Material

- `private-docs/`: internal planning, working notes, and archived non-public docs; keep this directory untracked
