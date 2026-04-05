# Architecture

Pantry is a small monorepo with three runtime services and a shared deployment layer.

## Runtime Services

- `apps/web`: Next.js application for setup, admin, pantry, recipe, import, and AI pages
- `apps/api`: FastAPI application for auth, household access, pantry, recipe, import, diagnostics, and admin APIs
- `apps/worker`: Python worker for queued import processing and other background tasks

## Supporting Services

- PostgreSQL stores application data
- Redis supports worker coordination and lightweight runtime state
- Docker Compose provides the local development stack and the released self-hosted stack

## Operating Boundaries

- Household-scoped access is enforced server-side in the API
- Uploaded files are stored outside web-served paths and treated as hostile input
- Pantry inventory is tracked through stock lots rather than flattened counters
- Imports stay review-first; Pantry does not create stock from an import until the user confirms it
- The public deployment path uses versioned GHCR images plus repo-hosted install and update assets

## Deployment Files

- [compose.yml](/Users/robinbrown/Documents/GitHub/pantry/compose.yml): local source-based development stack
- [infra/compose/pantry.yml](/Users/robinbrown/Documents/GitHub/pantry/infra/compose/pantry.yml): released self-hosted stack
- [infra/env/pantry.env.example](/Users/robinbrown/Documents/GitHub/pantry/infra/env/pantry.env.example): released environment template
