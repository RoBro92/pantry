# Pantro

Pantro is a self-hosted household inventory application for tracking food, planning around what is already at home, and reducing avoidable waste.

It is built for local operation rather than hosted sync. This public repository ships the self-hosted, operator-managed Pantro product only: the web app, API, worker, Docker deployment assets, and the core contributor documentation needed to run and maintain it safely. It does not include hosted control-plane, billing, or other SaaS-only logic.

## What Pantro Includes

- Pantro inventory with households, rooms, storage locations, stock lots, and expiry tracking
- Bulk barcode entry with camera, USB wedge scanners, and manual fallback, plus sequential review before saving to the inventory
- Shopping lists with review and reconciliation flows
- Recipes with pantry coverage summaries
- Optional Open Food Facts lookup for product enrichment
- Optional AI product intelligence that classifies pantry products into structured recipe-matching metadata
- Guided first-run setup, including restore from a Pantro backup bundle
- Admin tools for users, backups, diagnostics, updates, SMTP, and optional AI provider configuration
- Optional guided household AI meal suggestions backed by an instance-level OpenAI, Claude, Ollama, or custom OpenAI-compatible provider, including pantry-aware recipe completion writeback

## Project Scope

- Self-hosted and operator-managed
- Optional AI features; the core product remains usable without AI
- No SaaS billing, hosted sync, or hosted control-plane logic in this repository
- No automatic updates; operators choose when to upgrade

## Quick Start

For a supported self-hosted install on Debian:

```bash
curl -fsSL https://raw.githubusercontent.com/RoBro92/pantry/main/infra/scripts/install-pantro.sh | bash
```

The installer prepares Docker, downloads the release assets, writes `.env`, generates required secrets, runs migrations, starts the stack, and runs a health check.

Open `http://<your-server>:3000/` when the installer finishes.

## Manual Installation

1. Download the release assets for the version you want to run.
2. Copy `infra/env/pantro.env.example` to `.env` in the install directory.
3. Set the required URLs, database password, and secret keys.
4. Start PostgreSQL and Redis, run the `migrate` job, then start the stack.

The full manual flow lives in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Updating

Pantro does not self-update. Operators update it deliberately:

```bash
./update-pantro.sh
```

That flow refreshes release assets by default, updates `PANTRO_VERSION`, pulls images, runs migrations, restarts services, and runs the bundled health check.

If you are upgrading an existing Pantry-named install, the legacy `./update-pantry.sh` wrapper remains supported during the migration.

## First Run

Fresh installs open into the setup flow. Pantro currently supports two install paths:

- Fresh install
- Restore from backup

Restore accepts Pantro backup bundle JSON files only. Uploaded bundles are validated and staged before any destructive action is applied.

## Local Development

Local branch work uses the Docker-based source stack that stays separate from the released self-hosted compose file in `infra/compose/pantro.yml`:

```bash
./pantro start --fresh
./pantro start --demo
```

- `fresh` resets the local stack to the setup flow
- `demo` resets and seeds a repeatable local demo account set
- each `./pantro start --fresh` or `./pantro start --demo` run replaces the full local web/api/worker stack and resets the local Docker volumes before seeding the selected mode
- `./pantro reset --fresh` or `./pantro reset --demo` switches modes without forcing image rebuilds
- `./pantro stop` stops and removes the full local stack cleanly
- `./pantro rebuild` is only needed after Dockerfile or dependency changes
- `./pantro status` shows the current local stack state
- `./pantro logs` follows the local service logs
- the helper uses `local.env` first when present, otherwise `.env.local`, then `.env`, and creates `.env.local` from `.env.local.example` on first run
- optional `PANTRO_LOCAL_AI_*` and `PANTRO_LOCAL_SMTP_*` values in `local.env` or `.env.local` can pre-populate fresh setup and local demo-mode AI/SMTP settings through Pantro’s normal encrypted local config storage
- legacy `PANTRY_LOCAL_AI_*` and `PANTRY_LOCAL_SMTP_*` keys are also accepted by the local source stack for backward compatibility
- local AI and SMTP bootstrap runs an initial validation pass after demo seed or setup finalize so the admin UI reflects the current status without an extra manual check
- web changes hot reload in the browser, API changes auto-reload, and worker source changes restart the worker process in the dev stack
- demo credentials stay in the public repo for contributor use: `demoadmin` / `demopass` and `demouser` / `demopass`
- the legacy `./pantry` helper still works as a compatibility alias

Contributor workflow details live in [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).

## Public Docs

- [LICENSE](LICENSE)
- [SUPPORT.md](SUPPORT.md)
- [docs/FILE_MAP.md](docs/FILE_MAP.md)
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/RELEASE_RUNBOOK.md](docs/RELEASE_RUNBOOK.md)
- [docs/SECURITY.md](docs/SECURITY.md)
- [docs/VERSIONING.md](docs/VERSIONING.md)
- [docs/MIGRATION_TO_PANTRO.md](docs/MIGRATION_TO_PANTRO.md)
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)
- [docs/TEST_STRATEGY.md](docs/TEST_STRATEGY.md)
- [AGENTS.md](AGENTS.md)
