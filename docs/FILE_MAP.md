# File Map

Quick reference for the public repository layout.

## Application Code

- `apps/web/`: Next.js frontend
- `apps/api/`: FastAPI backend, Alembic migrations, API tests, pantry enrichment services, release metadata logic, backup/restore services, and setup finalisation logic
- `apps/worker/`: background worker
- `packages/shared-types/`: shared TypeScript constants and types

## Deployment And Operations

- `compose.yml`: local source-based development stack
- `infra/compose/pantry.yml`: released self-hosted Compose stack
- `infra/env/pantry.env.example`: released environment template
- `infra/docker/`: Dockerfiles for local and released images
- `infra/scripts/`: install, update, smoke-check, healthcheck, and local helper scripts

## Documentation

- `README.md`: overview and first-run guidance
- `docs/ARCHITECTURE.md`: runtime and setup architecture
- `docs/CONTRIBUTING.md`: local setup and contribution flow
- `docs/DEPLOYMENT.md`: self-hosted deployment guidance
- `docs/VERSIONING.md`: release metadata policy and update visibility model
- `docs/SECURITY.md`: upload, restore, and operator safety notes
- `docs/TEST_STRATEGY.md`: validation expectations
- `docs/PROJECT_STATE.md`: current milestone state and recent validations
- `docs/DECISIONS.md`: durable architecture decisions
