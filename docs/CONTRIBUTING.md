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
2. Choose one explicit development bootstrap mode:

```bash
./infra/scripts/dev-stack.sh start fresh
./infra/scripts/dev-stack.sh start demo
```

3. Open `http://localhost:3000/`.

Development bootstrap modes are local-only and intended for branch work against the source stack:

- `fresh` resets to an uninitialized first-run state and lands on the setup wizard at `/setup`
- `demo` resets the local database, seeds stable demo data, marks setup complete, and lands on `/login`
- the helper requires an explicit mode; do not rely on implicit local bootstrapping
- stop the stack with `./infra/scripts/dev-stack.sh down`
- follow logs with `./infra/scripts/dev-stack.sh logs`

Demo credentials:

- `robin` / `weymouth` for a local platform-admin convenience account
- `demoadmin` / `demopass` for the seeded demo platform admin
- `demouser` / `demopass` for the seeded demo household user

The local source stack is development-only:

- `web` runs `next dev` with Docker-friendly polling enabled so mounted file changes trigger hot reload.
- `api` runs `uvicorn --reload` with polling enabled so Python edits under `apps/api/app` and `apps/api/alembic` reload the server process.
- Workspace source is bind-mounted into the containers; dependency and Next caches stay in named volumes so rebuilds are not required for normal UI or API edits.
- the `fresh` and `demo` bootstrap commands call a development-only seed/reset path and do not change the public production or self-hosted install flow

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
./infra/scripts/dev-stack.sh down
```

## Pull Requests

- Keep pull requests small enough to review in one pass.
- Summarize the change, the validation run, and any doc updates.
- If public behavior, installation, validation, or repo workflow changed, update the matching public docs in the same pull request.
