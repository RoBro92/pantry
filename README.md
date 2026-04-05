# Pantry

Pantry is a self-hosted household inventory and meal management application designed to track food, reduce waste, and streamline day-to-day kitchen workflows.

---

## Features

- Pantry inventory with locations, stock lots, and expiry tracking  
- Recipe management with pantry coverage insights  
- Import and review flow for adding items  
- QR code location access (e.g. fridge, cupboard)  
- Admin diagnostics and system health visibility  
- Optional AI-powered suggestions (advisory only)  
- Fully self-hosted using Docker  

---

## Quick Start (Recommended)

Run the install script:

curl -fsSL https://raw.githubusercontent.com/<your-username>/pantry/main/infra/scripts/install-pantry.sh | bash

This will:
- Install Docker and required dependencies  
- Download the latest Pantry release  
- Configure the environment  
- Start the application  

---

## Manual Installation

git clone https://github.com/<your-username>/pantry.git  
cd pantry  

cp infra/env/pantry.env.example .env  

docker compose -f infra/compose/pantry.yml up -d  
docker compose exec api alembic upgrade head  

---

## Accessing Pantry

After installation, open:

http://<your-server-ip>:3000  

(Port may vary depending on your configuration.)

---

## Updating Pantry

./infra/scripts/update-pantry.sh  

This will:
- Pull the latest release image  
- Restart containers  
- Apply any required migrations  

---

## Versioning

- The running version is defined by the VERSION file  
- Visible in the admin UI and diagnostics  
- Update checks are advisory only (no automatic updates)  

---

## Configuration

Edit:

infra/env/pantry.env.example  

Key options include:
- Base URL (used for QR codes)  
- Database configuration  
- Optional AI provider settings  

---

## Troubleshooting

View logs:  
docker compose logs -f  

Restart services:  
docker compose restart  

Run health check:  
./infra/scripts/healthcheck-pantry.sh  

---

## License

See the LICENSE file for details.
