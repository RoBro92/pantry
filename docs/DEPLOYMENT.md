# Deployment

Pantry’s supported public deployment path is a self-hosted Docker installation using released images and repository-hosted deployment assets.

## Public Deployment Files

- `infra/compose/pantry.yml`
- `infra/env/pantry.env.example`
- `infra/scripts/install-pantry.sh`
- `infra/scripts/update-pantry.sh`
- `infra/scripts/healthcheck-pantry.sh`

## Scripted Install

For a supported Debian host:

```bash
curl -fsSL https://raw.githubusercontent.com/RoBro92/pantry/main/infra/scripts/install-pantry.sh | bash
```

The installer:

- checks Debian compatibility and network access
- installs Docker Engine and the Compose plugin when needed
- creates the install and data directories
- downloads `pantry.yml`, `pantry.env.example`, and helper scripts
- writes `.env` and generates required secrets
- pulls images, runs migrations, starts the stack, and runs a health check

When the install completes, open `http://<your-server>:3000/`.

## Manual Install

1. Download the release assets for the version you want to run.

```bash
export PANTRY_VERSION=0.1.0
mkdir -p /opt/pantry
cd /opt/pantry
curl -fsSLO "https://raw.githubusercontent.com/RoBro92/pantry/v${PANTRY_VERSION}/infra/compose/pantry.yml"
curl -fsSLo pantry.env.example "https://raw.githubusercontent.com/RoBro92/pantry/v${PANTRY_VERSION}/infra/env/pantry.env.example"
cp pantry.env.example .env
```

2. Edit `.env` and set at least:

- `PANTRY_VERSION`
- `PANTRY_IMAGE_NAMESPACE`
- `WEB_APP_URL`
- `API_BASE_URL`
- `NEXT_PUBLIC_API_BASE_URL`
- `PUBLIC_BROWSER_BASE_URL`
- `POSTGRES_PASSWORD`
- `SETTINGS_ENCRYPTION_KEY`
- `SESSION_SECRET_KEY`

3. Validate and start the stack.

```bash
docker compose --env-file .env -f pantry.yml config
docker compose --env-file .env -f pantry.yml pull
docker compose --env-file .env -f pantry.yml up -d postgres redis
docker compose --env-file .env -f pantry.yml --profile manual run --rm migrate
docker compose --env-file .env -f pantry.yml up -d
```

4. Verify the installation.

```bash
./healthcheck-pantry.sh --install-dir /opt/pantry
```

Then complete first-run setup in the browser.

## Updating

Pantry updates are explicit operator actions.

Update to the latest release:

```bash
./update-pantry.sh
```

Pin a specific release:

```bash
./update-pantry.sh --version 0.1.0
```

Keep your existing `pantry.yml` and `pantry.env.example` if you manage them manually:

```bash
./update-pantry.sh --skip-assets
```

The update script refreshes release assets by default, updates `PANTRY_VERSION`, pulls images, runs migrations, restarts services, and runs the bundled health check.

## Operator Fallback Commands

Bootstrap a platform admin from the API container:

```bash
docker compose --env-file .env -f pantry.yml run --rm api python -m app.cli bootstrap-platform-admin \
  --email admin@example.com \
  --display-name "Pantry Admin"
```

Reset a password from the API container:

```bash
docker compose --env-file .env -f pantry.yml run --rm api python -m app.cli reset-password \
  --email admin@example.com
```

## Restore Notes

- Restore currently accepts Pantry backup bundle JSON files only
- Restore is validated before application and remains an explicit operator action
- Uploaded restore bundles are staged under `BACKUP_STORAGE_ROOT`
- Self-service password reset stays disabled until SMTP is configured and enabled
