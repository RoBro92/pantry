# Deployment

Pantro’s supported public deployment path is a self hosted Docker installation using released images and repository hosted deployment assets. The public repository is self-hosted and operator-managed only: there is no hosted control plane and no auto-update service.

## Public Deployment Files

Canonical files:

- `infra/compose/pantro.yml`
- `infra/env/pantro.env.example`
- `infra/scripts/install-pantro.sh`
- `infra/scripts/update-pantro.sh`
- `infra/scripts/healthcheck-pantro.sh`

Compatibility aliases kept for existing installs:

- `infra/compose/pantry.yml`
- `infra/env/pantry.env.example`
- `infra/scripts/install-pantry.sh`
- `infra/scripts/update-pantry.sh`
- `infra/scripts/healthcheck-pantry.sh`

## Scripted Install

For a supported Debian host:

```bash
curl -fsSL https://raw.githubusercontent.com/RoBro92/pantry/main/infra/scripts/install-pantro.sh | bash
```

The installer:

- checks Debian compatibility and network access
- installs Docker Engine and the Compose plugin when needed
- creates the install and data directories
- downloads `pantro.yml`, `pantro.env.example`, and the legacy alias files
- writes `.env` and generates required secrets
- pulls images, runs migrations, starts the stack, and runs a health check

When the install completes, open `http://<your-ip>:3000/`.

## Manual Install

1. Download the release assets for the version you want to run.

```bash
export PANTRO_VERSION=0.2.0
mkdir -p /opt/pantro
cd /opt/pantro
curl -fsSLO "https://raw.githubusercontent.com/RoBro92/pantry/v${PANTRO_VERSION}/infra/compose/pantro.yml"
curl -fsSLo pantro.env.example "https://raw.githubusercontent.com/RoBro92/pantry/v${PANTRO_VERSION}/infra/env/pantro.env.example"
cp pantro.env.example .env
```

2. Edit `.env` and set at least:

- `PANTRO_VERSION`
- `PANTRO_IMAGE_NAMESPACE`
- `WEB_APP_URL`
- `API_BASE_URL`
- `PUBLIC_BROWSER_BASE_URL`
- `POSTGRES_PASSWORD`
- `SETTINGS_ENCRYPTION_KEY`
- `SESSION_SECRET_KEY`

Browser-side web requests use the web container's same-origin `/api/*` proxy in self-hosted releases. Operators only need `INTERNAL_API_BASE_URL=http://api:8000` so the web container can reach the API container internally.

3. Validate and start the stack.

```bash
docker compose --env-file .env -f pantro.yml config
docker compose --env-file .env -f pantro.yml pull
docker compose --env-file .env -f pantro.yml up -d postgres redis
docker compose --env-file .env -f pantro.yml --profile manual run --rm migrate
docker compose --env-file .env -f pantro.yml up -d
```

4. Verify the installation.

```bash
./healthcheck-pantro.sh --install-dir /opt/pantro
```

Then complete first-run setup in the browser.

## Updating

Pantro updates are explicit operator actions.

Update to the latest release:

```bash
./update-pantro.sh
```

Pin a specific release:

```bash
./update-pantro.sh --version 0.2.0
```

Keep your existing `pantro.yml` and `pantro.env.example` if you manage them manually:

```bash
./update-pantro.sh --skip-assets
```

If you are upgrading an older Pantry-named install, `./update-pantry.sh`, `pantry.yml`, and `pantry.env.example` remain supported as compatibility aliases for this migration.

The update script refreshes release assets by default, updates `PANTRO_VERSION`, pulls images, runs migrations, restarts services, and runs the bundled health check.

For a concise maintainer and operator checklist, see [docs/RELEASE_RUNBOOK.md](RELEASE_RUNBOOK.md).

## Operator Fallback Commands

Bootstrap a platform admin from the API container:

```bash
docker compose --env-file .env -f pantro.yml run --rm api python -m app.cli bootstrap-platform-admin \
  --email admin@example.com \
  --display-name "Pantro Admin"
```

Reset a password from the API container:

```bash
docker compose --env-file .env -f pantro.yml run --rm api python -m app.cli reset-password \
  --email admin@example.com
```

## Restore Notes

- Restore currently accepts Pantro backup bundle JSON files only
- Restore is validated before application and remains an explicit operator action
- Uploaded restore bundles are staged under `BACKUP_STORAGE_ROOT`
- Admin household restore creates a new household only and does not merge into an existing household
- Self-service password reset stays disabled until SMTP is configured, enabled, and tested successfully
