# File Map

Quick reference for the public repository layout.

## Product Code

- `apps/web/`: Next.js frontend
- `apps/api/`: FastAPI backend, Alembic migrations, and API test suite
- `apps/api/app/services/product_intelligence.py`: pantry product AI classification, staleness checks, and manual run orchestration
- `apps/worker/`: background worker
- `packages/shared-types/`: shared TypeScript types and constants
- `apps/api/app/services/development_seed.py`: public contributor seed and fresh/demo bootstrap data
- `apps/api/app/services/ai_*.py`, `apps/api/app/services/recipe_suggestion_providers.py`, and `apps/api/app/services/ai_providers/`: AI provider config, pantry-aware meal context assembly, prompt building, provider adapters, and recipe suggestion foundations
- `apps/api/app/services/ai_providers/openai_compat.py`: Pantry-owned OpenAI structured-output schema normalization, model-profile hints, and request/error compatibility helpers
- `apps/web/components/admin-ai-config-form.tsx` and `apps/web/components/setup-wizard.tsx`: admin AI/provider setup UX and first-run setup flows, including SMTP connectivity testing
- `apps/web/components/household-ai-meal-planner.tsx` and `apps/web/components/meal-suggestion-complete-dialog.tsx`: guided household AI meal suggestion flow, shortlist/detail UI, and explicit pantry stock deduction confirmation

## Deployment And Release Files

- `compose.yml`: local Docker-based contributor stack base
- `compose.dev.yml`: local bind-mount and reload overrides for live development
- `infra/compose/pantry.yml`: released self-hosted stack
- `infra/env/pantry.env.example`: released environment template
- `infra/docker/`: Dockerfiles for local and released images
- `pantry`: repo-root local development wrapper
- `infra/scripts/`: install, update, health check, smoke check, release, and local helper scripts
- `infra/scripts/dev-stack.sh`: local contributor helper behind the repo-root wrapper for `fresh`, `demo`, rebuild, logs, and stop flows
- `.github/workflows/`: pull request validation and release publishing workflows

## Public Documentation

- `README.md`: product overview, install entry point, and docs index
- `AGENTS.md`: public repository working rules
- `docs/ARCHITECTURE.md`: high level service and deployment layout
- `docs/CONTRIBUTING.md`: contributor workflow and local development commands
- `docs/DEPLOYMENT.md`: self hosted install and update guidance
- `docs/SECURITY.md`: safe operation and data handling notes
- `docs/TEST_STRATEGY.md`: proportionate validation guidance
- `docs/VERSIONING.md`: release and update model
