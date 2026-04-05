# Deployment

Pantry’s supported public deployment path is a self-hosted Docker installation using released GHCR images and repo-hosted deployment assets.

## Public Deployment Files

- [infra/compose/pantry.yml](/Users/robinbrown/Documents/GitHub/pantry/infra/compose/pantry.yml)
- [infra/env/pantry.env.example](/Users/robinbrown/Documents/GitHub/pantry/infra/env/pantry.env.example)
- [infra/scripts/install-pantry.sh](/Users/robinbrown/Documents/GitHub/pantry/infra/scripts/install-pantry.sh)
- [infra/scripts/update-pantry.sh](/Users/robinbrown/Documents/GitHub/pantry/infra/scripts/update-pantry.sh)
- [infra/scripts/healthcheck-pantry.sh](/Users/robinbrown/Documents/GitHub/pantry/infra/scripts/healthcheck-pantry.sh)

## Scripted Install

For a fresh Debian system:

```bash
curl -fsSL https://raw.githubusercontent.com/RoBro92/pantry/main/infra/scripts/install-pantry.sh -o /tmp/install-pantry.sh
chmod +x /tmp/install-pantry.sh
sudo /tmp/install-pantry.sh
```

The installer:

- verifies Debian and supported architecture
- checks GitHub and GHCR access
- installs Docker Engine and the Docker Compose plugin if needed
- creates the install directory and persistent data paths
- downloads `pantry.yml` and `pantry.env.example`
- creates `.env` and generates required secrets
- pulls the selected release images
- runs migrations, starts the stack, and performs a health check

## Manual Install

1. Download the target release assets:

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

3. Validate and start the stack:

```bash
docker compose --env-file .env -f pantry.yml config
docker compose --env-file .env -f pantry.yml pull
docker compose --env-file .env -f pantry.yml up -d postgres redis
docker compose --env-file .env -f pantry.yml --profile manual run --rm migrate
docker compose --env-file .env -f pantry.yml up -d
```

4. Verify the install:

```bash
curl -fsS http://YOUR_HOST:8000/api/health
docker compose --env-file .env -f pantry.yml exec -T worker python -m worker.main --status
```

Then complete first-run setup at `http://YOUR_HOST:3000/setup`.

## Updates

Pantry updates are explicit operator actions.

Scripted update:

```bash
./update-pantry.sh
```

Pin a specific release:

```bash
./update-pantry.sh --version 0.1.0
```

The update script refreshes release assets by default, updates `PANTRY_VERSION`, pulls images, runs migrations, restarts services, and checks health.

If you maintain a custom `pantry.yml`, use:

```bash
./update-pantry.sh --skip-assets
```

Manual updates follow the same sequence:

1. Back up PostgreSQL data and import storage.
2. Download the new release assets.
3. Review `.env` against the updated example.
4. Update `PANTRY_VERSION`.
5. Pull, migrate, restart, and verify.

## Health Checks And Admin Commands

Health check:

```bash
./healthcheck-pantry.sh --install-dir /opt/pantry
```

CLI bootstrap fallback:

```bash
docker compose --env-file .env -f pantry.yml run --rm api python -m app.cli bootstrap-platform-admin \
  --email admin@example.com \
  --display-name "Pantry Admin"
```

Password reset:

```bash
docker compose --env-file .env -f pantry.yml run --rm api python -m app.cli reset-password \
  --email admin@example.com
```
