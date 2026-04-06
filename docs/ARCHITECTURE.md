# Architecture

Pantry is a small monorepo with three runtime services and a staged first-run setup layer.

## Runtime Services

- `apps/web`: Next.js application for login, setup, admin, pantry, recipe, import, and AI pages
- `apps/api`: FastAPI application for auth, setup, admin, diagnostics, pantry, recipe, and import APIs
- `apps/worker`: Python worker for background import processing and related jobs

## Supporting Services

- PostgreSQL stores Pantry domain data plus staged setup state
- Redis supports worker coordination and runtime state
- Docker Compose provides local development and released self-hosted stacks

## Setup Architecture

- Fresh installs enter through `/`
- If setup is incomplete, Pantry routes users into the first-run wizard
- Wizard progress is stored in a dedicated `setup_states` record
- Staged setup data is kept separate from live household/user/settings tables
- Final completion writes live records in one controlled transactional flow and only then marks setup complete

## Operating Boundaries

- Household scoping is enforced server-side
- Imports remain review-first
- Uploaded files are treated as hostile input
- Secrets are encrypted before being stored in database-backed configuration or staged setup state
- Provider-specific AI details stay in the configuration layer, not core pantry domain models
