# Tech Stack

## Application Stack

- Web: Next.js 15 with React 19 and TypeScript.
- API: FastAPI on Python 3.12 with SQLAlchemy 2, Alembic, and structured logging.
- Worker: Python background process sharing SQLAlchemy-backed data access and Redis-backed coordination.
- Shared frontend constants: TypeScript workspace package.

## Data And Infrastructure

- PostgreSQL for relational persistence.
- Redis for background work support and ephemeral coordination.
- Docker Compose for local development and baseline self-hosted deployment.
- GitHub Container Registry is the planned distribution target for versioned runtime images.
- GitHub Releases is the planned source for published release metadata and operator-visible update checks.

## Testing And Validation

- Pytest for API and service-level validation.
- Playwright for Docker-backed end-to-end coverage.
- Repo scripts for deterministic E2E seeding, worker one-shot execution, and smoke checks.

## Operational Defaults

- Structured JSON logs for API and worker.
- Environment-variable-driven runtime configuration.
- Runtime version injection from the repository `VERSION` file via environment variables.
- Reverse proxy and TLS managed outside the application stack.

## Deliberately Minimal Or Planned

- No frontend component framework added yet.
- No GHCR publishing or GitHub Releases automation committed yet.
- No in-app update-available check implemented yet.
- No production deployment profile beyond the local/self-hosted Compose baseline.
