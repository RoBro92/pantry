# Pantry

Pantry is a self-hosted household inventory and meal management application designed to track food, reduce waste, and streamline day-to-day kitchen workflows.

## Features

- Pantry inventory with locations, stock lots, and expiry tracking
- Recipe management with pantry coverage insights
- Import and review flow for adding items
- QR code location access (e.g. fridge, cupboard)
- Admin diagnostics and system health visibility
- Optional AI-powered suggestions (advisory only)
- Fully self-hosted using Docker

## Quick Start (Recommended)

Run the install script:

```bash
curl -fsSL https://raw.githubusercontent.com/RoBro92/pantry/main/infra/scripts/install-pantry.sh | bash
```

This will:
- install Docker and required dependencies
- download the latest Pantry release
- configure the environment
- start the application

## Manual Installation

```bash
git clone https://github.com/RoBro92/pantry.git
cd pantry

cp infra/env/pantry.env.example .env

docker compose -f infra/compose/pantry.yml up -d
docker compose exec api alembic upgrade head
```

## Accessing Pantry

After installation, open:

```text
http://<your-server-ip>:3000
```

(Port may vary depending on your configuration.)

## Updating Pantry

```bash
./infra/scripts/update-pantry.sh
```

This will:
- pull the latest release image
- restart containers
- apply any required migrations

## Versioning

- The running version is defined by the `VERSION` file
- Visible in the admin UI and diagnostics
- Update checks are advisory only (no automatic updates)

## Configuration

Edit:

```text
infra/env/pantry.env.example
```

Key options include:
- base URL used for QR codes
- database configuration
- optional AI provider settings

## Troubleshooting

View logs:

```bash
docker compose logs -f
```

Restart services:

```bash
docker compose restart
```

Run health check:

```bash
./infra/scripts/healthcheck-pantry.sh
```

## License

See the LICENSE file for details.
