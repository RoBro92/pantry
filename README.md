# Pantry

Pantry is a self-hosted household inventory application for tracking food, planning around what is already at home, and reducing avoidable waste.

It is built for local operation rather than hosted sync. This public repository ships the self-hosted, operator-managed Pantry product only: the web app, API, worker, Docker deployment assets, and the core contributor documentation needed to run and maintain it safely. It does not include hosted control-plane, billing, or other SaaS-only logic.

## What Pantry Includes

- Pantry inventory with households, rooms, storage locations, stock lots, and expiry tracking
- Shopping lists with review and reconciliation flows
- Recipes with pantry coverage summaries
- Optional Open Food Facts lookup for product enrichment
- Optional AI product intelligence that classifies pantry products into structured recipe-matching metadata
- Guided first-run setup, including restore from a Pantry backup bundle
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
curl -fsSL https://raw.githubusercontent.com/RoBro92/pantry/main/infra/scripts/install-pantry.sh | bash
```

The installer prepares Docker, downloads the release assets, writes `.env`, generates required secrets, runs migrations, starts the stack, and runs a health check.

Open `http://<your-server>:3000/` when the installer finishes.

## Manual Installation

1. Download the release assets for the version you want to run.
2. Copy `infra/env/pantry.env.example` to `.env` in the install directory.
3. Set the required URLs, database password, and secret keys.
4. Start PostgreSQL and Redis, run the `migrate` job, then start the stack.

The full manual flow lives in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Updating

Pantry does not self-update. Operators update it deliberately:

```bash
./update-pantry.sh
```

That flow refreshes release assets by default, updates `PANTRY_VERSION`, pulls images, runs migrations, restarts services, and runs the bundled health check.

## First Run

Fresh installs open into the setup flow. Pantry currently supports two install paths:

- Fresh install
- Restore from backup

Restore accepts Pantry backup bundle JSON files only. Uploaded bundles are validated and staged before any destructive action is applied.

## Local Development

Local branch work uses the Docker-based source stack that stays separate from the released self-hosted compose file in `infra/compose/pantry.yml`:

```bash
./pantry start --fresh
./pantry start --demo
```

- `fresh` resets the local stack to the setup flow
- `demo` resets and seeds a repeatable local demo account set
- each `./pantry start --fresh` or `./pantry start --demo` run replaces the full local web/api/worker stack and resets the local Docker volumes before seeding the selected mode
- `./pantry reset --fresh` or `./pantry reset --demo` switches modes without forcing image rebuilds
- `./pantry stop` stops and removes the full local stack cleanly
- `./pantry rebuild` is only needed after Dockerfile or dependency changes
- `./pantry status` shows the current local stack state
- `./pantry logs` follows the local service logs
- the helper uses `.env.local` first, falls back to `.env`, and creates `.env.local` from `.env.example` on first run
- web changes hot reload in the browser, API changes auto-reload, and worker source changes restart the worker process in the dev stack
- demo credentials stay in the public repo for contributor use: `demoadmin` / `demopass` and `demouser` / `demopass`

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
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)
- [docs/TEST_STRATEGY.md](docs/TEST_STRATEGY.md)
- [AGENTS.md](AGENTS.md)
