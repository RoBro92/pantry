# Deployment

## Local Self-Hosted Development

1. Copy `.env.example` to `.env`.
2. Replace placeholder secrets and review ports, URLs, and session settings.
3. Run `docker compose up -d --build`.
4. Run `docker compose run --rm api alembic upgrade head`.
5. Open `http://localhost:3000/setup` to create the first platform admin.
6. Use the installation console to create a household, create or reset users, and assign memberships.
7. Set the public/browser base URL before relying on QR/location links outside localhost.

If you run web build or typecheck commands on the host instead of inside Docker, use `Node.js 20.x`
and `npm 10.x`. The Compose web image already pins that runtime.

## Practical First-Run Checklist

- Confirm the web app loads on `/` and `/setup`.
- Create exactly one initial platform admin through `/setup` or the CLI fallback.
- Create at least one household and one non-admin user if multiple people will use the install.
- Assign memberships before expecting `/app` household cards to appear for those users.
- Configure the public/browser URL in `/admin/settings` before sharing location links.
- Leave AI and SMTP disabled unless the operator has configured reachable providers.

The local stack exposes:

- Web on port `3000`
- API on port `8000`
- PostgreSQL on port `5432`
- Redis on port `6379`

## Environment Variables

Current key variables:

- `ENVIRONMENT`
- `DEPLOYMENT_MODE`
- `DEMO_MODE_ENABLED`
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

For self-hosted operators, the most important values to review early are:

- `SESSION_SECRET_KEY`
- `SESSION_HTTPS_ONLY`
- `INTERNAL_API_BASE_URL`
- `PUBLIC_BROWSER_BASE_URL`
- `DEPLOYMENT_MODE`
- `POSTGRES_PASSWORD`

For the local Docker Compose stack, the web service should use `INTERNAL_API_BASE_URL=http://api:8000` so server-side Next.js requests reach the API over the Compose network. `compose.yml` now defaults the web container to that value unless you override it explicitly.

`DEPLOYMENT_MODE` is validated as `self_hosted`, `demo`, or `saas`. The `saas` mode is a placeholder boundary only in this public repo; it does not enable billing, hosted onboarding, or SaaS-only UI.

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

## Production Release Path

The intended self-hosted production path is:

1. Validate `main`.
2. Bump `VERSION`.
3. Publish a GitHub Release and matching version tags.
4. Publish versioned container images to GHCR.
5. Let Pantry compare its current version against release metadata and show an update-available notice to platform admins.
6. Let the operator update deployment manifests manually and roll forward or back deliberately.

This repository does not implement the full update-check system yet. The current codebase only exposes the running version in the UI, API health output, and diagnostics.

## Planned Production/LXC Target

The intended production target after the release milestone is a Docker-based deployment on the user's LXC cluster, with:

- reverse proxy and TLS handled outside Pantry
- persistent PostgreSQL storage
- persistent import storage outside ephemeral container filesystems
- Redis for worker coordination
- image tags pinned to released GHCR versions rather than local source builds
- operator-managed secrets, backups, and upgrade windows

## LXC Readiness Checklist

Before calling Pantry production-ready for LXC-hosted deployment, the repo still needs:

- versioned GHCR image publishing
- GitHub Releases-based update metadata
- a documented production Compose or equivalent deployment profile
- backup and restore guidance for PostgreSQL and import storage
- explicit upgrade and rollback instructions for operators
- clearer production environment variable examples

## Intentionally Not Implemented Yet

- unattended auto-updates
- release-channel switching inside the app
- hosted control-plane deployment tooling
- public production runbooks for any future SaaS environment
