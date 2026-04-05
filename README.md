# Pantry

Pantry is a self-hosted household pantry manager for tracking what you have, where it is stored, what is running low, and what needs review before it becomes inventory.

It ships as a multi-service Docker application with a web UI, API, worker, PostgreSQL, and Redis. Released images are published to GHCR, while install and update assets stay in this repository.

## What Pantry Includes Today

- Household pantry locations and stock-lot tracking
- Recipe storage with pantry coverage and shopping-gap summaries
- Reviewed import flows for supported file types before stock is created
- Platform admin setup, user management, household management, and diagnostics
- Optional AI provider configuration for read-only suggestions
- Versioned Docker deployment assets and explicit operator-run updates

## Quick Start

### Scripted Install

For a fresh Debian LXC or Debian host:

```bash
curl -fsSL https://raw.githubusercontent.com/RoBro92/pantry/main/infra/scripts/install-pantry.sh -o /tmp/install-pantry.sh
chmod +x /tmp/install-pantry.sh
sudo /tmp/install-pantry.sh
```

The installer downloads the public deployment assets, creates `.env`, generates required secrets, pulls the selected release images, runs migrations, starts the stack, and leaves `update-pantry.sh` and `healthcheck-pantry.sh` in the install directory.

### Manual Install

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

Finish first-run setup at `http://YOUR_HOST:3000/setup`.

Full deployment instructions: [docs/DEPLOYMENT.md](/Users/robinbrown/Documents/GitHub/pantry/docs/DEPLOYMENT.md)

## Updating

Pantry does not self-update. Updates are explicit operator actions.

Scripted update from the install directory:

```bash
./update-pantry.sh
```

Or pin a specific release:

```bash
./update-pantry.sh --version 0.1.0
```

Manual updates follow the same pattern: back up data, download the target release assets, review `.env`, update `PANTRY_VERSION`, pull images, run migrations, restart, and verify health.

Versioning details: [docs/VERSIONING.md](/Users/robinbrown/Documents/GitHub/pantry/docs/VERSIONING.md)

## Basic Usage

1. Open `/setup` on a new install and create the first platform admin.
2. Create users and households from the admin console.
3. Open a household and add locations, products, and stock.
4. Add recipes or upload reviewed imports.
5. Use diagnostics and health checks before and after upgrades.

CLI fallback for first admin creation:

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

## Troubleshooting

- API health: `http://YOUR_HOST:8000/api/health`
- Setup page: `http://YOUR_HOST:3000/setup`
- Login page: `http://YOUR_HOST:3000/login`
- Install health check: `./healthcheck-pantry.sh --install-dir /opt/pantry`
- Local development stack: `docker compose up -d --build`

If `docker compose ... config` fails, fix `.env` first. If containers start but the app is unavailable, check `docker compose ps`, API health, and the worker status reported by the bundled health check.

## Important Files

- [infra/compose/pantry.yml](/Users/robinbrown/Documents/GitHub/pantry/infra/compose/pantry.yml): released self-hosted Compose stack
- [infra/env/pantry.env.example](/Users/robinbrown/Documents/GitHub/pantry/infra/env/pantry.env.example): self-hosted environment template
- [infra/scripts/install-pantry.sh](/Users/robinbrown/Documents/GitHub/pantry/infra/scripts/install-pantry.sh): fresh install helper
- [infra/scripts/update-pantry.sh](/Users/robinbrown/Documents/GitHub/pantry/infra/scripts/update-pantry.sh): update helper
- [infra/scripts/healthcheck-pantry.sh](/Users/robinbrown/Documents/GitHub/pantry/infra/scripts/healthcheck-pantry.sh): post-install and post-update verifier
- [compose.yml](/Users/robinbrown/Documents/GitHub/pantry/compose.yml): local source-based development stack

## Development

For local source-based development:

```bash
cp .env.example .env
docker compose up -d --build
docker compose run --rm api alembic upgrade head
```

Use `Node.js 20.x` and `npm 10.x` for host-side web commands.

Contributor notes: [docs/CONTRIBUTING.md](/Users/robinbrown/Documents/GitHub/pantry/docs/CONTRIBUTING.md)
