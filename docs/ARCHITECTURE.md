# Architecture

Pantry is a small monorepo with three runtime services, a staged first-run setup layer, and operator-controlled lifecycle tooling.

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
- The wizard supports both `fresh_install` and `restore_backup` installation modes
- Wizard progress is stored in a dedicated `setup_states` record
- Staged setup data is kept separate from live household/user/settings tables
- Restore uploads are validated and staged separately from live data until finalization
- Final completion writes live records in one controlled transactional flow and only then marks setup complete

## Lifecycle And Recovery

- Release visibility is advisory-only and centered on GitHub Releases metadata
- Optional `release.json` assets can enrich published release notes and operator commands
- GHCR is treated as image hosting, not a metadata source
- Backup export uses Pantry-native JSON bundles
- Restore currently supports full instance bundles only and requires schema parity
- Household export exists for retention and future recovery work, but not for direct restore in this milestone

## Admin Management

- Platform admins manage users, households, memberships, updates, backups, SMTP, AI, settings, and diagnostics from the admin console
- Household membership removal and household deletion are guarded by server-side safety checks and audit logging
- Destructive flows require explicit confirmation in the UI and on the server

## Operating Boundaries

- Household scoping is enforced server-side
- Imports remain review-first
- Uploaded files are treated as hostile input
- Backup uploads are validated as data only, staged in quarantine, and never executed
- Secrets are encrypted before being stored in database-backed configuration or staged setup state
- Provider-specific AI details stay in the configuration layer, not core pantry domain models
