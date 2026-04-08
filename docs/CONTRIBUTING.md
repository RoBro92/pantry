# Contributing

Keep changes focused, reviewable, and aligned with the shipped self-hosted product.

## Workflow

Pantry uses a branch and pull request workflow.

1. Start from an up to date `main`.
2. Create a short-lived branch for one focused change.
3. Use a lightweight branch name such as `feature/...`, `fix/...`, `docs/...`, or `release/...`.
4. Implement the change and run the relevant local validation.
5. Open a pull request, review the diff and checks, then merge back to `main`.

Do not use direct-to-`main` development for normal changes.

## Local Setup

1. Copy `infra/env/pantry.env.example` to `.env` if you are using the local source-based stack.
2. Start the stack with `docker compose up -d --build`.
3. Run migrations with `docker compose run --rm api alembic upgrade head`.
4. Open `http://localhost:3000/`.

Fresh installs should land in the first-run setup wizard. Completed installs should land on the login page.

## Expectations

- Keep `apps/web`, `apps/api`, and `apps/worker` responsibilities clear
- Update public docs when runtime, install, or contributor workflows change
- Add or update tests when user-visible behavior changes
- Keep internal-only planning notes, scratchpads, and workspace files out of the public repo
- Store internal planning material under `private-docs/` or another private location rather than `docs/`
- Review Codex-generated diffs, workflows, and docs before merging

## Validation

Start with [docs/TEST_STRATEGY.md](/Users/robinbrown/Documents/GitHub/pantry/docs/TEST_STRATEGY.md).

Common commands:

```bash
npm run typecheck:web
npm run build:web
cd apps/api && pytest -q
./infra/scripts/smoke-check.sh
docker compose down
```

## Pull Requests

- Keep pull requests small enough to review in one pass.
- Summarize the change, the validation run, and any doc updates.
- If public behavior, installation, validation, or repo workflow changed, update the matching public docs in the same pull request.
