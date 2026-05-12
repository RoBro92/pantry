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

When the install completes, open the configured public URL.

For production use, serve Pantro through HTTPS. Production API startup now requires `SESSION_HTTPS_ONLY=true` so signed session cookies are only sent over secure connections. The installer refuses non-HTTPS public URLs, and the updater stops before changing the stack if an existing `.env` still points browser traffic at `http://`. Browser camera scanning and installable PWA behaviour also require a secure context in production; localhost remains supported for development.

## Manual Install

1. Download the release assets for the version you want to run.

```bash
export PANTRO_VERSION=0.2.1
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
- `SESSION_HTTPS_ONLY=true`
- `INTERNAL_API_PROXY_TOKEN`

Browser-side web requests use the web container's same-origin `/api/*` proxy in self-hosted releases. Operators need `INTERNAL_API_BASE_URL=http://api:8000` so the web container can reach the API container internally, and a random `INTERNAL_API_PROXY_TOKEN` shared by the web and API containers so API rate limits can trust the client scope forwarded by the web proxy.

Unsafe direct API requests are protected by Origin/Referer checks. `WEB_APP_URL` and
`API_BASE_URL` are allowed automatically; add comma-separated extra browser origins
to `CSRF_TRUSTED_ORIGINS` only when a reverse proxy or alternate hostname is meant
to make credentialed API calls. Keep `CSRF_PROTECTION_ENABLED=true` for normal
self-hosted deployments. Login, password reset, and first-run setup mutation rate
limits use Redis by default; tune the `*_RATE_LIMIT_*` values in `.env` if needed.

The released web, API, worker, and migration containers run as the numeric app user
configured by `PANTRO_APP_UID` and `PANTRO_APP_GID` (`10001:10001` by default).
The installer and updater adjust only the Pantro-managed import and backup data
directories for that user. Do not change PostgreSQL or Redis data directory
ownership to the app UID.

## Reverse Proxy Examples

Pantro expects TLS to terminate at your reverse proxy. Forward browser traffic to
the web container, not directly to the API, unless you are intentionally exposing
the API for operator automation. The proxy must preserve the public host and
scheme so the web API proxy and CSRF checks see the same origin as the browser.

Nginx:

```nginx
server {
  listen 443 ssl http2;
  server_name pantro.example.com;

  ssl_certificate /etc/letsencrypt/live/pantro.example.com/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/pantro.example.com/privkey.pem;

  location / {
    proxy_pass http://127.0.0.1:3000;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-Host $http_host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }
}
```

Caddy:

```caddyfile
pantro.example.com {
  reverse_proxy 127.0.0.1:3000 {
    header_up Host {host}
    header_up X-Forwarded-Host {host}
    header_up X-Forwarded-Proto https
  }
}
```

For a non-standard HTTPS port such as `https://pantry.example.com:8443`, include
the port in `WEB_APP_URL`, `API_BASE_URL`, and `PUBLIC_BROWSER_BASE_URL`. If any
other trusted browser origin can make credentialed API calls, add that exact
scheme, host, and port to `CSRF_TRUSTED_ORIGINS`.

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

Before updating:

1. Run `./healthcheck-pantro.sh --install-dir /opt/pantro`.
2. Record the current `PANTRO_VERSION` from `.env`.
3. Back up PostgreSQL data and Pantro-managed import storage. Keep the backup
   until the new version passes health checks.

Update to the latest release:

```bash
./update-pantro.sh
```

Pin a specific release:

```bash
./update-pantro.sh --version 0.2.1
```

Keep your existing `pantro.yml` and `pantro.env.example` if you manage them manually:

```bash
./update-pantro.sh --skip-assets
```

If you are upgrading an older Pantry-named install, `./update-pantry.sh`, `pantry.yml`, and `pantry.env.example` remain supported as compatibility aliases for this migration.

The update script refreshes release assets by default, updates `PANTRO_VERSION`, sets `SESSION_HTTPS_ONLY=true`, pulls images, runs migrations, restarts services, and runs the bundled health check. Before updating older installs, set `PUBLIC_BROWSER_BASE_URL` or `WEB_APP_URL` to the HTTPS URL served by your reverse proxy.

Before upgrading to the release that introduces the stock quantity constraint, repair any rows where `stock_lots.quantity < 0`. The migration stops with an explicit error if negative stock quantities are present, because Pantro now enforces non-negative stock at the database layer.

Before upgrading to the release that introduces the active stock merge index,
repair duplicate active `stock_lots` rows with the same household, product,
location, unit, and expiry. The migration stops with an explicit error if those
duplicates are present.

If an update fails, inspect the service state before taking rollback action:

```bash
docker compose --env-file .env -f pantro.yml ps
docker compose --env-file .env -f pantro.yml logs --tail=200 web api worker
./healthcheck-pantro.sh --install-dir /opt/pantro --timeout 180
```

Rollback depends on whether migrations applied. If migrations did not run or did
not apply, restore the pre-update `.env` and compose asset backups, pin
`PANTRO_VERSION` to the previous version, and restart the stack:

```bash
docker compose --env-file .env -f pantro.yml up -d --remove-orphans
```

If migrations applied or data looks inconsistent, restore the pre-update
PostgreSQL and import-storage backup first, then restore the previous `.env` and
compose assets before restarting the previous version. Do not run an older image
against a database that has already been migrated forward unless the release
notes explicitly say that downgrade path is supported.

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
