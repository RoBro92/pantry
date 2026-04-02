# Pantry Agent Rules

`AGENTS.md` is the primary durable instruction file for Codex in this repository. Future milestone prompts should stay short and rely on this file plus the referenced docs instead of re-stating the operating rules.

Pantry is the self-hosted-first foundation for a future SaaS-capable product. Work directly in this repository and keep the structure ready for later hosted expansion without implementing SaaS-only internals prematurely.

## Operating Order

1. Inspect the current repository state before making changes.
2. Read [docs/FILE_MAP.md](/Users/robinbrown/Documents/GitHub/pantry/docs/FILE_MAP.md) before large edits.
3. Read [docs/PROJECT_STATE.md](/Users/robinbrown/Documents/GitHub/pantry/docs/PROJECT_STATE.md) and any directly relevant docs before implementing a milestone.
4. Work on `main` unless the user explicitly tells you to use another branch.
5. Modify the repository directly. Do not create prompt dumps, planning markdown files, or meta-instruction files unless the user explicitly asks for them.

## Non-Negotiables

- Treat `VERSION` as the single source of truth for the application version.
- Keep `apps/web`, `apps/api`, and `apps/worker` clearly separated.
- Keep private operational or SaaS-only material in `private-docs/` and never commit it.
- Do not put provider-specific business logic into core domain code.
- Do not add database schema changes without a matching migration strategy.
- Treat uploads as hostile input in both code and docs.
- Enforce tenant scoping server-side for every household-scoped resource.
- Preserve multi-tenant safety in API routes, services, jobs, and admin flows.
- Use structured logs for system activity and keep audit/domain events conceptually separate.
- Never log secrets, tokens, passwords, or raw credential-bearing URLs.
- Prefer small focused modules over giant multi-purpose files.

## Implementation Conventions

- Keep docs and code aligned in the same change when possible.
- Record durable architecture choices in [docs/DECISIONS.md](/Users/robinbrown/Documents/GitHub/pantry/docs/DECISIONS.md).
- Keep business logic out of presentational React components.
- Use opaque external IDs for tenant-facing entities.
- Document new environment variables and local commands in the repo docs.
- Make direct repo changes rather than stopping at a plan when the task is implementable.
- Commit at sensible logical checkpoints when the task is large enough to benefit from it. Keep commits scoped and descriptive.

## Milestone Validation Workflow

Use [docs/TEST_STRATEGY.md](/Users/robinbrown/Documents/GitHub/pantry/docs/TEST_STRATEGY.md) as the concrete validation policy. At minimum, future Codex sessions must do the following before calling a milestone complete:

1. Run setup needed for the changed area.
2. Start the Docker stack when services or integration checks require it.
3. Run migrations or other setup steps required by the change.
4. Run lint, typecheck, and test commands relevant to the changed files and services.
5. Run smoke checks for every changed service or feature surface.
6. Run E2E checks when user-facing flows changed and E2E coverage exists.
7. Shut the Docker stack down after validation unless the user explicitly asks to leave it running.
8. Report the validation performed and the outcome.

Do not treat work as complete without performing validation and reporting the result. If a required validation step cannot run, state the blocker clearly and record it in `docs/PROJECT_STATE.md`.

## Required Project State Updates

When repo shape, architecture direction, or milestone status changes, update [docs/PROJECT_STATE.md](/Users/robinbrown/Documents/GitHub/pantry/docs/PROJECT_STATE.md) in the same change. Include:

- What changed.
- Validation commands run and their results.
- Any blockers, known gaps, or skipped checks.
- The most sensible next step.
