# Pantry

Pantry is a self-hosted-first pantry management application designed for households that want reliable inventory tracking, import workflows, recipe support, and future AI-assisted features without locking the core product to a single hosting or provider model.

This repository starts with the self-hosted foundation and keeps the architecture ready for later SaaS deployment modes. The current state includes pantry, recipe, import, AI, diagnostics, SMTP, QR/location, and Docker-backed Playwright E2E foundations without introducing hosted-only product logic.

The current repository includes:

- `apps/web`: Next.js frontend
- `apps/api`: FastAPI backend with SQLAlchemy, Alembic, session auth, and admin CLI
- `apps/worker`: Python background worker
- `packages/shared-types`: minimal shared TypeScript constants and types
- `compose.yml`: local development stack with web, API, worker, PostgreSQL, and Redis
- `docs/`: product, architecture, security, and roadmap documentation
- `private-docs/`: local-only space for private operational or SaaS notes

## Product Direction

- Self-hosted first, SaaS-ready later
- Multi-household from the start
- Roles: `platform_admin`, `household_admin`, `household_user`
- Session-based web login with secure password hashing
- Opaque external IDs for tenant-facing identity and household records
- AI provider abstraction from day one
- Initial provider targets: Ollama and OpenAI-compatible APIs
- Uploaded files treated as hostile input
- Structured logging and audit/event thinking from the start

## Release Posture

- `VERSION` is the canonical application version.
- The current version is already exposed in the landing page, authenticated app shell, API health response, and admin diagnostics view.
- The recommended next release milestone is a GitHub Releases and GHCR-based self-hosted workflow, with manual operator updates rather than an auto-updater.
- See [docs/VERSIONING.md](/Users/robinbrown/Documents/GitHub/pantry/docs/VERSIONING.md) and [docs/DEPLOYMENT.md](/Users/robinbrown/Documents/GitHub/pantry/docs/DEPLOYMENT.md) for the release and deployment plan.

## First-Time Self-Hosted Setup

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Review the placeholder secrets and ports in `.env`, especially `SESSION_SECRET_KEY`,
   `POSTGRES_PASSWORD`, and any future provider credentials.

Local host-side web commands currently expect `Node.js 20.x` with `npm 10.x`. The Docker stack
already uses Node 20, so Docker-backed setup and E2E runs are the safest default on newer host
machines.

3. Start the local stack:

```bash
docker compose up -d --build
docker compose run --rm api alembic upgrade head
```

4. Open `http://localhost:3000/setup` and create the first platform admin in the browser.

5. In the installation console:

- create at least one household
- create or reuse the user accounts that will sign in
- assign memberships before expecting household dashboards to show data
- set the public browser URL before printing or sharing QR/location links

6. Sign in through `http://localhost:3000/login` and start using pantry, recipe, import, AI,
   diagnostics, and QR/location flows.

## Service URLs

- Web: `http://localhost:3000`
- API health: `http://localhost:8000/api/health`
- Setup: `http://localhost:3000/setup`
- Login: `http://localhost:3000/login`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

## CLI Fallbacks

Create the first platform admin from the CLI instead of the browser:

```bash
docker compose run --rm api python -m app.cli bootstrap-platform-admin \
  --email admin@example.com \
  --display-name "Pantry Admin"
```

Reset an existing user password:

```bash
docker compose run --rm api python -m app.cli reset-password \
  --email admin@example.com
```

Both commands will prompt for a password if one is not supplied as a flag.

## Repository Layout

```text
apps/
  api/           FastAPI service
  web/           Next.js frontend
  worker/        Python background worker
docs/            Product, architecture, and engineering docs
infra/
  docker/        Dockerfiles for local development
  scripts/       Small repository utility scripts
packages/
  shared-types/  Shared TypeScript constants and types
private-docs/    Local-only, gitignored operational notes
VERSION          Single source of truth for the app version
```

## Useful Commands

```bash
docker compose up -d --build
docker compose run --rm api alembic upgrade head
docker compose down
npm install
npm run dev:web
cd apps/api && python3 -m pytest
```

For local API tests outside Docker:

```bash
python3 -m pip install -r apps/api/requirements-dev.txt
cd apps/api && pytest
```

Important environment variables:

- `NEXT_PUBLIC_API_BASE_URL`: browser-facing API URL for frontend requests.
- `INTERNAL_API_BASE_URL`: server-side API URL used by Next.js server components. In Docker Compose this should point to `http://api:8000`.
- `SESSION_SECRET_KEY`: secret used to sign web sessions. Replace the placeholder before any real deployment.
- `SESSION_HTTPS_ONLY`: set to `true` behind HTTPS.
- `DEPLOYMENT_MODE`: validated as `self_hosted`, `demo`, or `saas`, with `saas` remaining a placeholder boundary in this public repo.
- `DEMO_MODE_ENABLED`: optional demo-mode config flag; this milestone does not implement demo reset or disposable-data automation.

## Documentation

Start with these files:

- [docs/PROJECT_STATE.md](/Users/robinbrown/Documents/GitHub/pantry/docs/PROJECT_STATE.md)
- [docs/FILE_MAP.md](/Users/robinbrown/Documents/GitHub/pantry/docs/FILE_MAP.md)
- [docs/ARCHITECTURE.md](/Users/robinbrown/Documents/GitHub/pantry/docs/ARCHITECTURE.md)
- [docs/DEPLOYMENT.md](/Users/robinbrown/Documents/GitHub/pantry/docs/DEPLOYMENT.md)
- [docs/VERSIONING.md](/Users/robinbrown/Documents/GitHub/pantry/docs/VERSIONING.md)
- [docs/SECURITY.md](/Users/robinbrown/Documents/GitHub/pantry/docs/SECURITY.md)
- [docs/MILESTONES.md](/Users/robinbrown/Documents/GitHub/pantry/docs/MILESTONES.md)
