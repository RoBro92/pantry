# Contributing

## Expectations

- Keep changes scoped and coherent.
- Update relevant docs when architecture or setup changes.
- Preserve the separation between web, API, and worker code.
- Avoid large speculative implementations when a documented scaffold is enough.
- Keep the public `docs/` tree limited to user-relevant or open-source-safe developer documentation.
- Put internal prompts, planning scaffolds, SaaS-only operational notes, and other private material in local `private-docs/`.

## Local Setup

1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. Use the web app at `http://localhost:3000` and API health endpoint at `http://localhost:8000/api/health`.

## Engineering Rules

- No giant files.
- No schema changes without migrations.
- Structured logging only; never log secrets.
- Keep business logic out of presentational UI components.
- Treat uploads as hostile input.
- Use opaque external IDs for tenant-facing entities.
- Keep private operational or SaaS docs out of the public repo.
