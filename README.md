# Pantry

Pantry is a self-hosted-first pantry management application designed for households that want reliable inventory tracking, import workflows, recipe support, and future AI-assisted features without locking the core product to a single hosting or provider model.

This repository starts with the self-hosted foundation and keeps the architecture ready for later SaaS deployment modes. The current scaffold includes:

- `apps/web`: Next.js frontend
- `apps/api`: FastAPI backend
- `apps/worker`: Python background worker
- `packages/shared-types`: minimal shared TypeScript constants and types
- `compose.yml`: local development stack with web, API, worker, PostgreSQL, and Redis
- `docs/`: product, architecture, security, and roadmap documentation
- `private-docs/`: local-only space for private operational or SaaS notes

## Product Direction

- Self-hosted first, SaaS-ready later
- Multi-household from the start
- Roles: `platform_admin`, `household_admin`, `household_user`
- AI provider abstraction from day one
- Initial provider targets: Ollama and OpenAI-compatible APIs
- Uploaded files treated as hostile input
- Structured logging and audit/event thinking from the start

## Local Development

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Review the placeholder secrets and ports in `.env`.

3. Start the local stack:

```bash
docker compose up --build
```

4. Open the services:

- Web: `http://localhost:3000`
- API health: `http://localhost:8000/api/health`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

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
docker compose up --build
docker compose down
npm install
npm run dev:web
python3 -m venv .venv
```

The Python services currently run most easily through Docker Compose because the repo does not yet include a unified local Python environment manager.

## Documentation

Start with these files:

- [docs/PROJECT_STATE.md](/Users/robinbrown/Documents/GitHub/pantry/docs/PROJECT_STATE.md)
- [docs/FILE_MAP.md](/Users/robinbrown/Documents/GitHub/pantry/docs/FILE_MAP.md)
- [docs/ARCHITECTURE.md](/Users/robinbrown/Documents/GitHub/pantry/docs/ARCHITECTURE.md)
- [docs/SECURITY.md](/Users/robinbrown/Documents/GitHub/pantry/docs/SECURITY.md)
- [docs/MILESTONES.md](/Users/robinbrown/Documents/GitHub/pantry/docs/MILESTONES.md)

