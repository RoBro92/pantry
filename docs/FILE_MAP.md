# File Map

This is the quick reference for the public repository layout.

## Application Code

- `apps/web/`: Next.js frontend
- `apps/api/`: FastAPI backend, Alembic migrations, and API tests
- `apps/worker/`: background worker
- `packages/shared-types/`: shared TypeScript constants and types

## Deployment And Operations

- `compose.yml`: local development stack
- `infra/compose/pantry.yml`: released self-hosted Compose stack
- `infra/env/pantry.env.example`: released self-hosted environment template
- `infra/docker/`: Dockerfiles for local and released images
- `infra/scripts/install-pantry.sh`: fresh install helper
- `infra/scripts/update-pantry.sh`: update helper
- `infra/scripts/healthcheck-pantry.sh`: install and upgrade health check
- `infra/scripts/validate-release.sh`: release validation helper for maintainers

## Documentation

- `README.md`: product overview and install/update guidance
- `docs/DEPLOYMENT.md`: self-hosted install and update instructions
- `docs/VERSIONING.md`: release and update model
- `docs/SECURITY.md`: repository-level security expectations
- `docs/CONTRIBUTING.md`: local setup and contribution guidance
- `docs/TEST_STRATEGY.md`: proportionate validation guidance for changes
