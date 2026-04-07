# Pantry

Pantry is a self-hosted household inventory and meal management application for tracking food, reducing waste, and keeping day-to-day kitchen workflows clear.

## Features

- Pantry inventory with rooms, storage locations, stock lots, and expiry tracking
- Recipe management with pantry coverage insights
- Review-first import flows
- QR location access
- Diagnostics, update visibility, and manual update guidance
- Pantry-native backup export plus guarded restore foundations
- Optional AI-powered suggestions
- Guided first-run setup and login flow, including restore-from-backup

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/RoBro92/pantry/main/infra/scripts/install-pantry.sh | bash
```

The installer prepares Docker, writes environment defaults, pulls the release assets, runs migrations, and starts the stack.

## Manual Installation

```bash
git clone https://github.com/RoBro92/pantry.git
cd pantry

cp infra/env/pantry.env.example .env

docker compose -f infra/compose/pantry.yml up -d
docker compose exec api alembic upgrade head
```

## First Run

Open:

```text
http://<your-server-ip>:3000
```

Pantry now uses:

- `/` as the default entry point
- the first-run wizard when setup is incomplete
- the login page when setup is complete

The setup wizard stages progress until the final confirmation step. It walks through install selection, admin and user setup, dietary preferences, the first household with rooms and storage locations, and optional instance settings before writing anything live.

Pantry supports two first-run paths:

- `Fresh install`
- `Restore from backup`

Restore currently accepts Pantry-native full instance JSON backup bundles only. Uploaded restore files are validated, staged in quarantine, and never executed as code.

## Pantry Workflow

The household pantry page is built as one searchable pantry view. Use `Search` to find products by name or alias, review every stock lot with its room, storage location, dates, and notes, and use `Add product` to create a product and its first stock lot in one flow.

## Updating Pantry

```bash
./infra/scripts/update-pantry.sh
```

Pantry does not self-update. Platform admins can review the current version, latest published release metadata, changelog summaries, breaking change notes, and operator commands from the admin `Updates` page.

## Backups And Recovery

Platform admins can use the admin `Backups` page to:

- export a full instance Pantry backup bundle
- export a household-specific Pantry bundle for retention or inspection
- upload and validate a full instance restore bundle before applying it deliberately

Current restore support is limited to Pantry backup bundle v1 JSON files from the same schema revision.

## Configuration

Edit:

```text
infra/env/pantry.env.example
```

Key options include:

- `WEB_APP_URL`
- `API_BASE_URL`
- `NEXT_PUBLIC_API_BASE_URL`
- `PUBLIC_BROWSER_BASE_URL`
- database credentials
- optional AI provider settings
- optional SMTP settings

## Validation And Local Development

See:

- [docs/CONTRIBUTING.md](/Users/robinbrown/Documents/GitHub/pantry/docs/CONTRIBUTING.md)
- [docs/DEPLOYMENT.md](/Users/robinbrown/Documents/GitHub/pantry/docs/DEPLOYMENT.md)
- [docs/ARCHITECTURE.md](/Users/robinbrown/Documents/GitHub/pantry/docs/ARCHITECTURE.md)
- [docs/TEST_STRATEGY.md](/Users/robinbrown/Documents/GitHub/pantry/docs/TEST_STRATEGY.md)

## Troubleshooting

```bash
docker compose logs -f
docker compose restart
./infra/scripts/healthcheck-pantry.sh
```

## Versioning

The running version is defined by the `VERSION` file and surfaced across the app, diagnostics, and updates UI.

See also:

- [docs/VERSIONING.md](/Users/robinbrown/Documents/GitHub/pantry/docs/VERSIONING.md)
- [docs/SECURITY.md](/Users/robinbrown/Documents/GitHub/pantry/docs/SECURITY.md)
