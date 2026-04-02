# Pantry Agent Rules

This repository is the self-hosted-first foundation for Pantry. Future Codex sessions should work directly in the repo and keep the structure ready for later SaaS expansion without implementing SaaS-specific internals prematurely.

## Non-Negotiables

- Treat `VERSION` as the single source of truth for the application version.
- Keep `apps/web`, `apps/api`, and `apps/worker` clearly separated.
- Keep private operational or SaaS-only material in `private-docs/` and never commit it.
- Do not create prompt dumps, planning markdown files, or meta-instruction files unless explicitly requested.
- Do not put provider-specific business logic into core domain code.
- Do not add database schema changes without adding a matching migration strategy.
- Treat uploads as hostile input in both code and docs.
- Enforce tenant scoping server-side for every household-scoped resource.
- Use structured logs for system activity and keep audit/domain events conceptually separate.
- Never log secrets, tokens, passwords, or raw credential-bearing URLs.

## Working Conventions

- Read [docs/FILE_MAP.md](/Users/robinbrown/Documents/GitHub/pantry/docs/FILE_MAP.md) before large edits.
- Update [docs/PROJECT_STATE.md](/Users/robinbrown/Documents/GitHub/pantry/docs/PROJECT_STATE.md) when scaffolding or architecture direction changes.
- Record durable architecture choices in [docs/DECISIONS.md](/Users/robinbrown/Documents/GitHub/pantry/docs/DECISIONS.md).
- Keep docs and code aligned in the same change when possible.
- Prefer small modules over large multi-purpose files.
- Keep business logic out of presentational React components.
- Use opaque external IDs for tenant-facing entities.
- Document new environment variables and local commands in the repo docs.

