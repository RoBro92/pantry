# Codex Rules

These rules supplement [AGENTS.md](/Users/robinbrown/Documents/GitHub/pantry/AGENTS.md). Treat `AGENTS.md` as the primary durable instruction file and [docs/TEST_STRATEGY.md](/Users/robinbrown/Documents/GitHub/pantry/docs/TEST_STRATEGY.md) as the concrete validation policy.

## Required Behavior

- Inspect the current repo and relevant docs first.
- Work on `main` unless the user explicitly instructs otherwise.
- Modify the repository directly instead of creating prompt or planning files.
- Keep docs and code aligned in the same change when possible.
- Follow the validation and reporting workflow from `AGENTS.md` and `docs/TEST_STRATEGY.md`.

## Architecture Guardrails

- No provider-specific business logic in core domains.
- No tenant-scoping shortcuts or server-side isolation gaps.
- No logging of secrets.
- No database changes without a migration path.
- No giant files when a smaller module would be clearer.

## Documentation Guardrails

- Public docs should cover self-hosted use.
- Private SaaS and ops docs stay local in `private-docs/`.
- Update `docs/PROJECT_STATE.md`, `docs/FILE_MAP.md`, and `docs/DECISIONS.md` when the repo shape materially changes.
