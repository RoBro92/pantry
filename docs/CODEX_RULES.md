# Codex Rules

These rules are specific to this repository and supplement the root `AGENTS.md`.

## Required Behavior

- Work directly in the repository.
- Do not create prompt files, planning files, or meta-instruction markdown files unless explicitly requested.
- Prefer implementing the requested scaffold or change instead of stopping at a plan.
- Keep docs and code aligned.
- Keep services separated by responsibility.

## Architecture Guardrails

- No provider-specific business logic in core domains.
- No tenant-scoping shortcuts in the web layer.
- No logging of secrets.
- No database changes without a migration path.
- No giant files when a smaller module would be clearer.

## Documentation Guardrails

- Public docs should cover self-hosted use.
- Private SaaS and ops docs stay local in `private-docs/`.
- Update `docs/PROJECT_STATE.md`, `docs/FILE_MAP.md`, and `docs/DECISIONS.md` when the repo shape materially changes.

