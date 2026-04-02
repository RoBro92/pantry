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
- `DEPLOYMENT_MODE`
- `LOG_LEVEL`
- `WEB_PORT`
- `API_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `REDIS_URL`
- `WEB_APP_URL`
- `PUBLIC_BROWSER_BASE_URL`
- `NEXT_PUBLIC_API_BASE_URL`
- `INTERNAL_API_BASE_URL`
- `OLLAMA_BASE_URL`
- `OPENAI_COMPAT_BASE_URL`
- `OPENAI_COMPAT_API_KEY`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_FROM_NAME`
- `SMTP_SECURITY`
- `SMTP_ENABLED`
- `SMTP_TIMEOUT_SECONDS`
- `WORKER_POLL_INTERVAL_SECONDS`

For the local Docker Compose stack, the web service should use `INTERNAL_API_BASE_URL=http://api:8000` so server-side Next.js requests reach the API over the Compose network. `compose.yml` now defaults the web container to that value unless you override it explicitly.

## Instance Settings And Precedence

- The application now supports an installation-scoped public/browser base URL used for generated browser links and pantry location QR codes.
- The application also supports installation-scoped SMTP foundation settings for future password recovery and notification work.
- If `PUBLIC_BROWSER_BASE_URL` is set, it overrides the saved database value.
- If `SMTP_HOST` is set, the effective SMTP config is taken from `SMTP_*` environment variables instead of the saved database value.
- If no public/browser URL override or saved value exists, generated browser links fall back to `WEB_APP_URL`.
- SMTP passwords saved through the admin UI are encrypted at rest and redacted on readback; environment-provided SMTP passwords are never stored in the database.

## Hosting Boundary

- Application containers do not terminate TLS.
- Reverse proxy and certificates are external.
- Private hosted-operations runbooks must remain outside the public repo.
