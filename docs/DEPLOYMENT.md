# Deployment

## Supported Public Path

The supported public self-hosted path is:

- Docker Engine plus the Docker Compose plugin
- published GHCR images
- repo-hosted deployment assets and helper scripts
- explicit operator-run installs and updates

Pantry does not self-update, does not require local image builds, and does not ship hosted control-plane logic in this public repo.

Canonical public deployment files:

- `infra/compose/pantry.yml`
- `infra/env/pantry.env.example`
- `infra/scripts/install-pantry.sh`
- `infra/scripts/update-pantry.sh`
- `infra/scripts/healthcheck-pantry.sh`

## Scripted Install On A Fresh Debian LXC

1. Run the installer as root:

```bash
curl -fsSL https://raw.githubusercontent.com/RoBro92/pantry/main/infra/scripts/install-pantry.sh -o /tmp/install-pantry.sh
chmod +x /tmp/install-pantry.sh
sudo /tmp/install-pantry.sh
```

2. The installer will prompt for:

- Pantry version
- browser host or IP
- web port
- API port
- whether the install should use HTTPS URLs

3. The installer then:

- verifies Debian and a supported `amd64` or `arm64` architecture
- verifies GitHub and GHCR connectivity
- installs Docker Engine and the Docker Compose plugin if needed
- creates the install directory and persistent data directories
- places `pantry.yml`, `pantry.env.example`, `.env`, `update-pantry.sh`, and `healthcheck-pantry.sh` in the install directory
- generates `POSTGRES_PASSWORD`, `SETTINGS_ENCRYPTION_KEY`, and `SESSION_SECRET_KEY`
- pulls the pinned GHCR images
- runs migrations
- starts the stack
- verifies web, API, setup state, and worker status

4. Finish first-run setup in the browser at `/setup` or with the admin CLI fallback.

## Manual Install

### 1. Download the public assets for the target release

```bash
export PANTRY_VERSION=0.1.0
mkdir -p /opt/pantry
cd /opt/pantry
curl -fsSLO "https://raw.githubusercontent.com/RoBro92/pantry/v${PANTRY_VERSION}/infra/compose/pantry.yml"
curl -fsSLo pantry.env.example "https://raw.githubusercontent.com/RoBro92/pantry/v${PANTRY_VERSION}/infra/env/pantry.env.example"
cp pantry.env.example .env
```

### 2. Edit `.env`

Set at least:

- `PANTRY_VERSION`
- `PANTRY_IMAGE_NAMESPACE=ghcr.io/robro92`
- `WEB_APP_URL`
- `API_BASE_URL`
- `NEXT_PUBLIC_API_BASE_URL`
- `PUBLIC_BROWSER_BASE_URL`
- `POSTGRES_PASSWORD`
- `SETTINGS_ENCRYPTION_KEY`
- `SESSION_SECRET_KEY`
- `PANTRY_POSTGRES_DATA_DIR`
- `PANTRY_REDIS_DATA_DIR`
- `PANTRY_IMPORTS_DATA_DIR`

The public example defaults to direct access on ports `3000` and `8000`. If you later move Pantry behind a reverse proxy, update the public URLs and cookie settings deliberately.

### 3. Validate, pull, migrate, and start

```bash
docker compose --env-file .env -f pantry.yml config
docker compose --env-file .env -f pantry.yml pull
docker compose --env-file .env -f pantry.yml up -d postgres redis
docker compose --env-file .env -f pantry.yml --profile manual run --rm migrate
docker compose --env-file .env -f pantry.yml up -d
```

### 4. Verify health and complete setup

```bash
curl -fsS http://YOUR_HOST:8000/api/health
docker compose --env-file .env -f pantry.yml exec -T worker python -m worker.main --status
```

Then open:

- `http://YOUR_HOST:3000/`
- `http://YOUR_HOST:3000/setup`
- `http://YOUR_HOST:3000/login`
- `http://YOUR_HOST:8000/api/health`

## Update Flow

Pantry updates are manual and explicit.

### Scripted Update

From the install directory:

```bash
./update-pantry.sh
```

To target a specific release:

```bash
./update-pantry.sh --version 0.1.0
```

Default scripted update behavior:

- refresh `pantry.yml` and `pantry.env.example` from the tagged GitHub repo content
- update `PANTRY_VERSION` in `.env`
- pull the matching GHCR images
- run migrations
- restart services
- run the health check

If you intentionally maintain a custom `pantry.yml`, run:

```bash
./update-pantry.sh --skip-assets
```

### Manual Update

1. Check the latest release in `/admin`, `/admin/diagnostics`, or with `./infra/scripts/check-release-metadata.sh`.
2. Review the GitHub Release notes.
3. Back up PostgreSQL data and import storage.
4. Download the new `pantry.yml` and `pantry.env.example` from the target tag.
5. Review `.env` against the updated example.
6. Update `PANTRY_VERSION`.
7. Pull, migrate, restart, and verify:

```bash
docker compose --env-file .env -f pantry.yml pull
docker compose --env-file .env -f pantry.yml --profile manual run --rm migrate
docker compose --env-file .env -f pantry.yml up -d --remove-orphans
curl -fsS http://YOUR_HOST:8000/api/health
```

## Health Check And Admin Commands

Run the bundled health check at any time:

```bash
./healthcheck-pantry.sh --install-dir /opt/pantry
```

Preferred first admin path:

- open `/setup` in the browser

CLI fallback:

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

## Persistent Data And Backups

- PostgreSQL data must live on a persistent host path.
- Redis persistence is enabled in `pantry.yml` and should also use a persistent host path.
- Reviewed import files and derived import artifacts live in `PANTRY_IMPORTS_DATA_DIR`.
- Back up PostgreSQL and import storage together before every upgrade.

## Reverse Proxy And TLS Boundary

- Pantry containers do not terminate TLS.
- Reverse proxy and certificates stay outside the app stack.
- If you move from direct access to HTTPS behind a reverse proxy, update `WEB_APP_URL`, `API_BASE_URL`, `NEXT_PUBLIC_API_BASE_URL`, `PUBLIC_BROWSER_BASE_URL`, and `SESSION_HTTPS_ONLY=true`.

## Local Development

For local source-based development, keep using:

- `compose.yml`
- `.env.example`
- `docker compose up -d --build`
- `docker compose run --rm api alembic upgrade head`
