# Pantry

Pantry is a self-hosted household pantry manager for tracking what you have, where it is stored, what is running low, and what needs review before it becomes inventory.

It runs as a Docker-based application with a web app, API, worker, PostgreSQL, and Redis. Released container images are published to GHCR, and the install and update assets live in this repository.

## Features Available Today

- Pantry locations, products, and stock-lot tracking
- Recipe storage with pantry coverage and shopping-gap summaries
- Reviewed imports that require confirmation before creating stock
- First-run setup plus platform admin user and household management
- Diagnostics, health checks, and version-aware updates
- Optional AI provider configuration for read-only suggestions

## Install

### Scripted Install

For a fresh Debian host or Debian LXC:

```bash
curl -fsSL https://raw.githubusercontent.com/RoBro92/pantry/main/infra/scripts/install-pantry.sh -o /tmp/install-pantry.sh
chmod +x /tmp/install-pantry.sh
sudo /tmp/install-pantry.sh
```

The installer uses the public deployment assets in this repository:

- [infra/compose/pantry.yml](/Users/robinbrown/Documents/GitHub/pantry/infra/compose/pantry.yml)
- [infra/env/pantry.env.example](/Users/robinbrown/Documents/GitHub/pantry/infra/env/pantry.env.example)
- [infra/scripts/install-pantry.sh](/Users/robinbrown/Documents/GitHub/pantry/infra/scripts/install-pantry.sh)
- [infra/scripts/update-pantry.sh](/Users/robinbrown/Documents/GitHub/pantry/infra/scripts/update-pantry.sh)
- [infra/scripts/healthcheck-pantry.sh](/Users/robinbrown/Documents/GitHub/pantry/infra/scripts/healthcheck-pantry.sh)

It creates `.env`, generates required secrets, pulls the selected release images, runs migrations, starts the stack, and leaves the update and health-check scripts in the install directory.

### Manual Docker Compose Install

```bash
export PANTRY_VERSION=0.1.0
mkdir -p /opt/pantry
cd /opt/pantry
curl -fsSLO "https://raw.githubusercontent.com/RoBro92/pantry/v${PANTRY_VERSION}/infra/compose/pantry.yml"
curl -fsSLo pantry.env.example "https://raw.githubusercontent.com/RoBro92/pantry/v${PANTRY_VERSION}/infra/env/pantry.env.example"
cp pantry.env.example .env
```

Edit `.env`, then validate and start:

```bash
docker compose --env-file .env -f pantry.yml config
docker compose --env-file .env -f pantry.yml pull
docker compose --env-file .env -f pantry.yml up -d postgres redis
docker compose --env-file .env -f pantry.yml --profile manual run --rm migrate
docker compose --env-file .env -f pantry.yml up -d
```

Complete first-run setup at `http://YOUR_HOST:3000/setup`.

More detail: [docs/DEPLOYMENT.md](/Users/robinbrown/Documents/GitHub/pantry/docs/DEPLOYMENT.md)

## Updating Pantry

Pantry updates are explicit operator actions.

Run the bundled update helper from the install directory:

```bash
./update-pantry.sh
```

Or target a specific release:

```bash
./update-pantry.sh --version 0.1.0
```

Manual updates follow the same pattern: back up data, download the target release assets, review `.env`, update `PANTRY_VERSION`, pull images, run migrations, restart services, and verify health.

Version details: [docs/VERSIONING.md](/Users/robinbrown/Documents/GitHub/pantry/docs/VERSIONING.md)

## Basic Usage

1. Open `/setup` on a new install and create the first platform admin.
2. Create users and households from the admin console.
3. Open a household and add pantry locations, products, and stock.
4. Add recipes or upload reviewed imports.
5. Use diagnostics and the bundled health check after upgrades.

CLI fallback for first admin creation:

```bash
docker compose --env-file .env -f pantry.yml run --rm api python -m app.cli bootstrap-platform-admin \
  --email admin@example.com \
  --display-name "Pantry Admin"
```

## Main Docs

- [docs/DEPLOYMENT.md](/Users/robinbrown/Documents/GitHub/pantry/docs/DEPLOYMENT.md)
- [docs/VERSIONING.md](/Users/robinbrown/Documents/GitHub/pantry/docs/VERSIONING.md)
- [docs/SECURITY.md](/Users/robinbrown/Documents/GitHub/pantry/docs/SECURITY.md)
- [docs/ARCHITECTURE.md](/Users/robinbrown/Documents/GitHub/pantry/docs/ARCHITECTURE.md)

## Troubleshooting

- API health endpoint: `http://YOUR_HOST:8000/api/health`
- Setup page: `http://YOUR_HOST:3000/setup`
- Login page: `http://YOUR_HOST:3000/login`
- Bundled health check: `./healthcheck-pantry.sh --install-dir /opt/pantry`

If `docker compose --env-file .env -f pantry.yml config` fails, fix `.env` before starting services. If the stack starts but Pantry is unavailable, check `docker compose ps`, the API health endpoint, and the bundled health-check output.
