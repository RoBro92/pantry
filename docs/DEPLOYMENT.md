# Deployment

## Local Self-Hosted Development

1. Copy `.env.example` to `.env`.
2. Set safe local placeholders for database password and any future provider credentials.
3. Run `docker compose up --build`.

The local stack exposes:

- Web on port `3000`
- API on port `8000`
- PostgreSQL on port `5432`
- Redis on port `6379`

## Environment Variables

Current key variables:

- `ENVIRONMENT`
- `LOG_LEVEL`
- `WEB_PORT`
- `API_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `REDIS_URL`
- `WEB_APP_URL`
- `NEXT_PUBLIC_API_BASE_URL`
- `INTERNAL_API_BASE_URL`
- `OLLAMA_BASE_URL`
- `OPENAI_COMPAT_BASE_URL`
- `OPENAI_COMPAT_API_KEY`
- `WORKER_POLL_INTERVAL_SECONDS`

For the local Docker Compose stack, the web service should use `INTERNAL_API_BASE_URL=http://api:8000` so server-side Next.js requests reach the API over the Compose network. `compose.yml` now defaults the web container to that value unless you override it explicitly.

## Hosting Boundary

- Application containers do not terminate TLS.
- Reverse proxy and certificates are external.
- Private hosted-operations runbooks must remain outside the public repo.
