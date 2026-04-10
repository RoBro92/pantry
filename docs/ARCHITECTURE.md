# Architecture

Pantry is a small repo for a self hosted product with three runtime services and a shared deployment layer.

## Runtime Services

- `apps/web`: Next.js application for setup, authentication, pantry, shopping list, recipes, imports, and admin pages
- `apps/api`: FastAPI application for domain APIs, setup flows, admin operations, release metadata, backups, and authentication
- `apps/worker`: Python worker for background import and recipe URL processing

## Shared Infrastructure

- PostgreSQL stores Pantry domain and configuration data
- Redis supports worker coordination and runtime queues
- Docker Compose is used for both the stack

## Product Boundaries

- Pantry is self hosted and operator managed
- Household access is enforced server side
- Product identity stays Pantry owned even when external enrichment from Open Food Facts is linked
- Open Food Facts is optional advisory enrichment, not the source of truth for Pantry records
- AI support is optional, provider-abstracted, and currently limited to advisory read-only suggestions
- AI provider configuration is stored at installation scope today, with routing kept self-hosted and operator managed
- Uploaded files and restore bundles are treated as hostile input
- Updates are advisory and operator triggered; Pantry does not auto-update

## Setup And Recovery

- New installs route through a first run setup flow until initialization is complete
- Setup supports both a fresh install path and restore from a Pantry backup bundle
- Restore validation happens before any destructive action is applied
- Backup export and restore tooling is surfaced through the admin experience and CLI/container fallbacks

## Deployment Surfaces

- `compose.yml`: source-based local development stack
- `infra/compose/pantry.yml`: released self-hosted stack
- `infra/env/pantry.env.example`: released environment template
