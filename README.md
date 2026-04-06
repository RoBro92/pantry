# Pantry

Pantry is a self-hosted household inventory and meal management application for tracking food, reducing waste, and keeping day-to-day kitchen workflows clear.

## Features

- Pantry inventory with locations, stock lots, and expiry tracking
- Recipe management with pantry coverage insights
- Review-first import flows
- QR location access
- Diagnostics and installation visibility
- Optional AI-powered suggestions
- Guided first-run setup and login flow

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

The setup wizard stages progress until the final confirmation step. It only writes users, household data, settings, dietary preferences, and optional AI/SMTP configuration into live tables when you click `Complete Setup`.

## Updating Pantry

```bash
./infra/scripts/update-pantry.sh
```

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

The running version is defined by the `VERSION` file and surfaced across the app and diagnostics.
