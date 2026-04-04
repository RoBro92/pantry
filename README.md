# Pantry

Pantry is a self-hosted-first pantry management application for households that want reliable inventory tracking, reviewed imports, recipe support, and future AI-assisted features without giving up operator control.

This repository keeps the public deployment story conventional:

- published images come from GHCR
- deployment assets and helper scripts stay in this GitHub repository
- installs and updates are explicit operator actions
- Pantry does not self-update and does not require local image builds

## Repository Includes

- `apps/web`: Next.js frontend
- `apps/api`: FastAPI backend with SQLAlchemy, Alembic, session auth, and admin CLI
- `apps/worker`: Python background worker
- `packages/shared-types`: shared TypeScript constants and types
- `compose.yml`: local development stack
- `infra/compose/pantry.yml`: public self-hosted stack for versioned GHCR images
- `infra/env/pantry.env.example`: public self-hosted env template
- `infra/scripts/install-pantry.sh`: fresh Debian LXC installer
- `infra/scripts/update-pantry.sh`: explicit operator-run update helper
- `infra/scripts/healthcheck-pantry.sh`: self-hosted install health verifier
- `docs/`: product, architecture, and operational documentation
- `private-docs/`: local-only space for private notes

## Product Direction

- Self-hosted first, SaaS-ready later
- Multi-household from the start
- Roles: `platform_admin`, `household_admin`, `household_user`
- Session-based web login with secure password hashing
- Opaque external IDs for tenant-facing identity and household records
- AI provider abstraction from day one
- Initial provider targets: Ollama and OpenAI-compatible APIs
- Uploaded files treated as hostile input
- Structured logging and audit/event thinking from the start

## Release Posture

- `VERSION` is the canonical application version.
- The running version is exposed in the landing page, authenticated app shell, admin overview, admin diagnostics, API health, worker heartbeat, and structured service logs.
- Platform admins get a read-only GitHub Releases-based update check showing the current version, latest published version, and release-notes link when configured.
- Maintainers validate `main`, bump `VERSION`, tag `vX.Y.Z`, and let GitHub Actions publish versioned GHCR images and create or update the GitHub Release.
- Operators remain in control of updates by pulling a chosen version, running migrations, and restarting the stack manually.

See [docs/VERSIONING.md](/Users/robinbrown/Documents/GitHub/pantry/docs/VERSIONING.md) and [docs/DEPLOYMENT.md](/Users/robinbrown/Documents/GitHub/pantry/docs/DEPLOYMENT.md).

## Public Self-Hosted Install

### Scripted Install

For a fresh Debian LXC:

```bash
curl -fsSL https://raw.githubusercontent.com/RoBro92/pantry/main/infra/scripts/install-pantry.sh -o /tmp/install-pantry.sh
chmod +x /tmp/install-pantry.sh
sudo /tmp/install-pantry.sh
```

The installer:

- checks Debian and supported architecture
- checks GitHub and GHCR network access
- installs Docker Engine and the Docker Compose plugin if needed
- creates the Pantry install directory
- downloads or copies `pantry.yml` and `pantry.env.example`
- creates `.env`, generates secrets, and writes the selected URLs and ports
- pulls GHCR images, runs migrations, starts the stack, and runs a health check
- leaves `update-pantry.sh` and `healthcheck-pantry.sh` in the install directory

### Manual Install

1. Pick a release version and create an install directory.

```bash
export PANTRY_VERSION=0.1.0
mkdir -p /opt/pantry
cd /opt/pantry
```

2. Download the public deployment assets for that tag.

```bash
curl -fsSLO "https://raw.githubusercontent.com/RoBro92/pantry/v${PANTRY_VERSION}/infra/compose/pantry.yml"
curl -fsSLo pantry.env.example "https://raw.githubusercontent.com/RoBro92/pantry/v${PANTRY_VERSION}/infra/env/pantry.env.example"
cp pantry.env.example .env
```

3. Edit `.env` and set at least:

- `PANTRY_VERSION`
- `PANTRY_IMAGE_NAMESPACE=ghcr.io/robro92`
- `WEB_APP_URL`
- `API_BASE_URL`
- `NEXT_PUBLIC_API_BASE_URL`
- `PUBLIC_BROWSER_BASE_URL`
- `POSTGRES_PASSWORD`
- `SETTINGS_ENCRYPTION_KEY`
- `SESSION_SECRET_KEY`

4. Pull, migrate, and start:

```bash
docker compose --env-file .env -f pantry.yml config
docker compose --env-file .env -f pantry.yml pull
docker compose --env-file .env -f pantry.yml up -d postgres redis
docker compose --env-file .env -f pantry.yml --profile manual run --rm migrate
docker compose --env-file .env -f pantry.yml up -d
```

5. Verify `http://YOUR_HOST:8000/api/health` and finish setup at `http://YOUR_HOST:3000/setup`.

## Public Update Flow

Pantry updates stay manual and explicit.

### Scripted Update

From the install directory:

```bash
./update-pantry.sh
```

Or pin a specific version:

```bash
./update-pantry.sh --version 0.1.0
```

By default the update script refreshes `pantry.yml` and `pantry.env.example`, updates `PANTRY_VERSION`, pulls the versioned GHCR images, runs migrations, restarts services, and verifies health.

### Manual Update

1. Back up PostgreSQL data and import storage.
2. Download the updated `pantry.yml` and `pantry.env.example` from the target tag.
3. Review `.env` against the new example.
4. Update `PANTRY_VERSION`.
5. Pull, migrate, restart, and verify:

```bash
docker compose --env-file .env -f pantry.yml pull
docker compose --env-file .env -f pantry.yml --profile manual run --rm migrate
docker compose --env-file .env -f pantry.yml up -d --remove-orphans
curl -fsS http://YOUR_HOST:8000/api/health
```

## Reset And Admin Commands

Preferred first-run path:

- open `/setup` in the browser

CLI fallback:

```bash
docker compose --env-file .env -f pantry.yml run --rm api python -m app.cli bootstrap-platform-admin \
  --email admin@example.com \
  --display-name "Pantry Admin"
```

Reset an existing user password:

```bash
docker compose --env-file .env -f pantry.yml run --rm api python -m app.cli reset-password \
  --email admin@example.com
```

Health check:

```bash
./healthcheck-pantry.sh --install-dir /opt/pantry
```

## Local Development

1. Copy `.env.example` to `.env`.
2. Review placeholder secrets and ports.
3. Start the local stack:

```bash
docker compose up -d --build
docker compose run --rm api alembic upgrade head
```

4. Open `http://localhost:3000/setup`.

If you run web build or typecheck commands on the host instead of inside Docker, use `Node.js 20.x` and `npm 10.x`. The Docker web image already pins that runtime.

Local service URLs:

- Web: `http://localhost:3000`
- API health: `http://localhost:8000/api/health`
- Setup: `http://localhost:3000/setup`
- Login: `http://localhost:3000/login`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

## Repository Layout

```text
apps/
  api/           FastAPI service
  web/           Next.js frontend
  worker/        Python background worker
docs/            Product, architecture, and engineering docs
infra/
  compose/       Public self-hosted Compose assets
  docker/        Development and production Dockerfiles
  env/           Public self-hosted env examples
  scripts/       Operator and maintainer scripts
packages/
  shared-types/  Shared TypeScript constants and types
private-docs/    Local-only, gitignored operational notes
VERSION          Single source of truth for the app version
```

## Useful Commands

```bash
docker compose up -d --build
docker compose run --rm api alembic upgrade head
docker compose down
npm install
npm run dev:web
cd apps/api && python3 -m pytest
./infra/scripts/validate-release.sh
```

For local API tests outside Docker:

```bash
python3 -m pip install -r apps/api/requirements-dev.txt
cd apps/api && pytest
```

Important environment variables:

- `NEXT_PUBLIC_API_BASE_URL`
- `INTERNAL_API_BASE_URL`
- `SESSION_SECRET_KEY`
- `SESSION_HTTPS_ONLY`
- `RELEASE_CHECK_REPOSITORY`
- `RELEASE_CHECK_METADATA_URL`
- `DEPLOYMENT_MODE`
- `DEMO_MODE_ENABLED`

## Documentation

Start with these files:

- [docs/PROJECT_STATE.md](/Users/robinbrown/Documents/GitHub/pantry/docs/PROJECT_STATE.md)
- [docs/FILE_MAP.md](/Users/robinbrown/Documents/GitHub/pantry/docs/FILE_MAP.md)
- [docs/ARCHITECTURE.md](/Users/robinbrown/Documents/GitHub/pantry/docs/ARCHITECTURE.md)
- [docs/DEPLOYMENT.md](/Users/robinbrown/Documents/GitHub/pantry/docs/DEPLOYMENT.md)
- [docs/VERSIONING.md](/Users/robinbrown/Documents/GitHub/pantry/docs/VERSIONING.md)
- [docs/SECURITY.md](/Users/robinbrown/Documents/GitHub/pantry/docs/SECURITY.md)
- [docs/MILESTONES.md](/Users/robinbrown/Documents/GitHub/pantry/docs/MILESTONES.md)
