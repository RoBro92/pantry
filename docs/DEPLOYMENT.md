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
- `RELEASE_CHECK_REPOSITORY`
- `RELEASE_CHECK_METADATA_URL`
- `RELEASE_CHECK_TIMEOUT_SECONDS`

For self-hosted operators, the most important values to review early are:

- `SESSION_SECRET_KEY`
- `SESSION_HTTPS_ONLY`
- `INTERNAL_API_BASE_URL`
- `PUBLIC_BROWSER_BASE_URL`
- `DEPLOYMENT_MODE`
- `POSTGRES_PASSWORD`
- `PANTRY_VERSION` in the production env file when using pinned GHCR images

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

This repository does not implement automated publishing or unattended updates. It now implements the first advisory update-check layer plus production deployment assets for manual operator-controlled upgrades.
This repository now includes the first production and update foundations for that path:

- admin-visible advisory update checks powered by GitHub Releases metadata
- production Dockerfiles for web, API, and worker image publishing
- `infra/compose/production.yml` for pinned-image Docker deployment on an LXC host
- `infra/env/production.lxc.env.example` as the production environment template
- helper scripts for release manifests and manual metadata checks

## Production Docker On LXC

The recommended production path is Docker inside an operator-managed LXC, with Pantry staying application-only:

- reverse proxy and TLS stay outside the Pantry containers
- PostgreSQL, Redis, and import storage stay on persistent host-backed paths
- published GHCR images are pinned explicitly by `PANTRY_VERSION`
- migrations run as an explicit manual step through the `migrate` service
- application updates remain operator-triggered and reversible

### Production Files Added In This Pass

- `infra/compose/production.yml`
- `infra/env/production.lxc.env.example`
- `infra/docker/web.production.Dockerfile`
- `infra/docker/api.production.Dockerfile`
- `infra/docker/worker.production.Dockerfile`

### First Production Bring-Up

1. Copy `infra/env/production.lxc.env.example` to an operator-managed env file such as `.env.production`.
2. Replace every placeholder secret and domain value.
3. Create the host directories referenced by:
   - `PANTRY_POSTGRES_DATA_DIR`
   - `PANTRY_REDIS_DATA_DIR`
   - `PANTRY_IMPORTS_DATA_DIR`
4. Validate the rendered stack:

```bash
docker compose --env-file .env.production -f infra/compose/production.yml config
```

5. Pull the pinned images:

```bash
docker compose --env-file .env.production -f infra/compose/production.yml pull
```

6. Run migrations explicitly:

```bash
docker compose --env-file .env.production -f infra/compose/production.yml --profile manual run --rm migrate
```

7. Start the stack:

```bash
docker compose --env-file .env.production -f infra/compose/production.yml up -d
```

8. Verify `/`, `/login`, and `/api/health`, then sign in as a platform admin and check `/admin/diagnostics`.

## Persistent Volume Expectations

- PostgreSQL data must persist outside the container lifecycle.
- Redis persistence is enabled in the production compose profile and should use a host-backed directory.
- Reviewed-import source files and derived import artifacts must persist in `PANTRY_IMPORTS_DATA_DIR`.
- Operators should back up PostgreSQL and import storage together before upgrading.

## Manual Operator Update Workflow

Pantry intentionally keeps updates manual.

1. Check the available release in `/admin`, `/admin/diagnostics`, or with `./infra/scripts/check-release-metadata.sh owner/repo`.
2. Review release notes.
3. Back up PostgreSQL data and import storage.
4. Update `PANTRY_VERSION` in the production env file.
5. Pull the new pinned images:

```bash
docker compose --env-file .env.production -f infra/compose/production.yml pull
```

6. Run migrations:

```bash
docker compose --env-file .env.production -f infra/compose/production.yml --profile manual run --rm migrate
```

7. Restart the stack:

```bash
docker compose --env-file .env.production -f infra/compose/production.yml up -d
```

8. Verify:
   - `GET /api/health`
   - platform admin diagnostics
   - worker heartbeat visibility
   - login and basic pantry navigation

If a release must be rolled back, restore the prior backup set and set `PANTRY_VERSION` back to the earlier pinned image tag before bringing the stack up again.

## Intentionally Not Implemented Yet

- unattended auto-updates
- release-channel switching inside the app
- hosted control-plane deployment tooling
- public production runbooks for any future SaaS environment
