# Tech Stack

## Application Stack

- Web: Next.js with React and TypeScript.
- API: FastAPI on Python.
- Worker: Python background process.
- Shared frontend constants: TypeScript workspace package.

## Data And Infrastructure

- PostgreSQL for relational persistence.
- Redis for background work support and ephemeral coordination.
- Docker Compose for local development and baseline self-hosted deployment.

## Operational Defaults

- Structured JSON logs for API and worker.
- Environment-variable-driven runtime configuration.
- Reverse proxy and TLS managed outside the application stack.

## Deliberately Minimal For Now

- No ORM or migration tool selected yet.
- No auth provider or session package selected yet.
- No frontend component framework added yet.

