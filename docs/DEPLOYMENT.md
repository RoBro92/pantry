# Deployment

Pantry’s public deployment path is a self-hosted Docker installation using released images and repo-hosted deployment assets.

## Public Deployment Files

- [infra/compose/pantry.yml](/Users/robinbrown/Documents/GitHub/pantry/infra/compose/pantry.yml)
- [infra/env/pantry.env.example](/Users/robinbrown/Documents/GitHub/pantry/infra/env/pantry.env.example)
- [infra/scripts/install-pantry.sh](/Users/robinbrown/Documents/GitHub/pantry/infra/scripts/install-pantry.sh)
- [infra/scripts/update-pantry.sh](/Users/robinbrown/Documents/GitHub/pantry/infra/scripts/update-pantry.sh)
- [infra/scripts/healthcheck-pantry.sh](/Users/robinbrown/Documents/GitHub/pantry/infra/scripts/healthcheck-pantry.sh)

## Fresh Install

After the stack is up, open:

```text
http://YOUR_HOST:3000/
```

Pantry will:

- route to the setup wizard if setup is incomplete
- keep staged setup progress between refreshes
- finalize users, households, locations, settings, dietary preferences, and optional AI/SMTP configuration only when `Complete Setup` is clicked

## Manual Install Checklist

1. Download release assets.
2. Copy the environment example to `.env`.
3. Set at least:
   - `PANTRY_VERSION`
   - `WEB_APP_URL`
   - `API_BASE_URL`
   - `NEXT_PUBLIC_API_BASE_URL`
   - `PUBLIC_BROWSER_BASE_URL`
   - `POSTGRES_PASSWORD`
   - `SETTINGS_ENCRYPTION_KEY`
   - `SESSION_SECRET_KEY`
4. Pull images, run migrations, and start the stack.
5. Open the browser URL and complete first-run setup.

## Operational Commands

CLI bootstrap still exists as an operator fallback:

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
