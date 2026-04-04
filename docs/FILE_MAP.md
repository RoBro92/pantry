# File Map

## Root

- `VERSION`: canonical application version.
- `compose.yml`: local development stack.
- `.env.example`: environment variable template.
- `package.json`: workspace scripts, including web validation and Playwright E2E entrypoints.
- `infra/scripts/read-version.sh`: lightweight helper that reads the canonical repo version.
- `playwright.config.ts`: Docker-backed Playwright configuration.
- `README.md`: project overview and local setup.

## Applications

- `apps/web/`: Next.js frontend with login page, protected shell, household pantry and import pages, and platform admin pages.
- `apps/api/`: FastAPI backend with SQLAlchemy models, Alembic migrations, auth routes, pantry and import APIs, and CLI commands.
- `apps/worker/`: Python worker for queued import processing and future background work.

## Packages

- `packages/shared-types/`: shared TypeScript constants for deployment modes, roles, and domain entities.

## Infrastructure

- `infra/docker/`: Dockerfiles for web, API, and worker.
- `infra/scripts/`: small repository utility scripts such as version helpers, repeatable smoke checks, E2E seed setup, and worker-once helpers.
- `infra/scripts/e2e-reset-uninitialized.sh`: resets application data in the running Docker stack so Playwright can exercise first-run setup deterministically.

## Key Backend Paths

- `apps/api/alembic/`: migration environment and migration history.
- `apps/api/app/models/`: SQLAlchemy identity, tenancy, pantry, recipe, import, stock-lot, and audit-event models.
- `apps/api/app/models/ai_provider_config.py`: instance- and future household-scoped AI provider configuration model.
- `apps/api/app/models/feature_flag.py`: server-side feature-flag overrides for instance and household scopes.
- `apps/api/app/models/instance_setting.py`: installation-scoped public URL and SMTP foundation settings.
- `apps/api/app/models/usage_counter.py`: request metering and future quota-analysis foundation records.
- `apps/api/app/api/routes/`: health, auth, admin, and household routes.
- `apps/api/app/api/routes/health.py`: health endpoint exposing status, environment, request ID, and application version.
- `apps/api/app/api/routes/setup.py`: first-run setup status and one-time browser bootstrap routes.
- `apps/api/app/api/routes/ai_admin.py`: platform-admin AI provider configuration and health-check routes.
- `apps/api/app/api/routes/diagnostics_admin.py`: platform-admin diagnostics route built from measured runtime data only.
- `apps/api/app/api/routes/settings_admin.py`: platform-admin public/browser base URL route.
- `apps/api/app/api/routes/smtp_admin.py`: platform-admin SMTP configuration and connectivity-test routes.
- `apps/api/app/api/routes/location_links.py`: authenticated QR/location deep-link route.
- `apps/api/app/api/routes/ai_households.py`: household AI status and read-only suggestion routes.
- `apps/api/app/api/deps/`: auth and tenancy dependencies.
- `apps/api/app/api/routes/pantry.py`: household-scoped pantry routes for locations, products, stock lots, and pantry views.
- `apps/api/app/api/routes/recipes.py`: household-scoped recipe routes for list/detail, create/update, and URL import capture.
- `apps/api/app/api/routes/imports.py`: household-scoped reviewed-import upload, history, detail, line-review, and confirm routes.
- `apps/api/app/cli.py`: admin bootstrap and password reset commands.
- `apps/api/app/services/pantry_*.py`: pantry catalog, stock mutation, normalization, and query services.
- `apps/api/app/services/recipe_*.py`: recipe create/update, deterministic matching, coverage, shopping-gap derivation, and URL import capture.
- `apps/api/app/services/import_*.py`: safe upload storage, deterministic line matching, worker processing, review workflow, and import query builders.
- `apps/api/app/services/ai_*.py`: AI provider config resolution, pantry-context assembly, prompt contracts, and suggestion orchestration.
- `apps/api/app/services/instance_settings.py`: instance settings resolution with env-overrides, redaction, and encrypted SMTP secret handling.
- `apps/api/app/services/setup.py`: install-initialization summary and one-time platform-admin bootstrap service.
- `apps/api/app/services/platform_admin.py`: installation-level user, household, and membership management services.
- `apps/api/app/services/platform_features.py`: deployment-default plus scoped feature-flag resolution and enforcement helpers.
- `apps/api/app/services/usage_counters.py`: usage counter increments and non-enforcing quota-check skeletons.
- `apps/api/app/services/diagnostics.py`: platform-admin diagnostics assembly for app, worker, Redis, queue, DB, and config summaries.
- `apps/api/app/services/runtime_status.py`: Redis-backed worker heartbeat publishing and Redis health helpers.
- `apps/api/app/services/location_links.py`: QR-safe location route and browser-link builders.
- `apps/api/app/services/ai_providers/`: provider adapter abstractions plus Ollama and OpenAI-compatible implementations.
- `apps/api/tests/`: focused API tests for auth, tenancy, pantry, recipe, import, AI, diagnostics, SMTP, and QR/location-link flows.
- `tests/e2e/`: Playwright browser coverage for critical self-hosted flows against the Docker stack.

## Key Frontend Paths

- `apps/web/app/(auth)/login/page.tsx`: login page.
- `apps/web/app/setup/page.tsx`: first-run browser setup page for the initial platform admin.
- `apps/web/app/(dashboard)/`: authenticated shell, pantry pages, and platform admin pages.
- `apps/web/lib/app-config.ts`: frontend runtime configuration including exposed app version.
- `apps/web/app/(dashboard)/app/households/[householdExternalId]/page.tsx`: household pantry view with search, stock lots, near-expiry, and audit activity.
- `apps/web/app/locations/[locationRoute]/page.tsx`: authenticated location deep-link page used by QR/browser links.
- `apps/web/app/(dashboard)/app/households/[householdExternalId]/imports/`: import inbox/history and reviewed import detail pages.
- `apps/web/app/(dashboard)/app/households/[householdExternalId]/recipes/`: recipe list, create, detail, and edit pages.
- `apps/web/app/(dashboard)/admin/ai/page.tsx`: platform admin AI provider configuration page.
- `apps/web/app/(dashboard)/admin/diagnostics/page.tsx`: platform admin diagnostics page.
- `apps/web/app/(dashboard)/admin/settings/page.tsx`: platform admin public/browser base URL page.
- `apps/web/app/(dashboard)/admin/smtp/page.tsx`: platform admin SMTP configuration page.
- `apps/web/app/(dashboard)/app/households/[householdExternalId]/ai/page.tsx`: household AI suggestions page.
- `apps/web/components/import-upload-form.tsx`: upload form for queued reviewed imports.
- `apps/web/components/setup-bootstrap-form.tsx`: first-run platform-admin bootstrap form.
- `apps/web/components/import-review-panel.tsx`: line-review and confirm-to-pantry UI for an import job.
- `apps/web/components/pantry-controls.tsx`: pantry creation and add-stock controls.
- `apps/web/components/pantry-lot-actions.tsx`: inline remove and move stock actions.
- `apps/web/components/location-qr-card.tsx`: server-rendered QR display for pantry locations.
- `apps/web/components/recipe-form.tsx`: client-side manual recipe create/edit form with ingredient rows and pantry-product links.
- `apps/web/components/admin-ai-config-form.tsx`: platform admin AI config and health-check client form.
- `apps/web/components/admin-user-creation-form.tsx`: platform-admin user creation form.
- `apps/web/components/admin-household-management-panel.tsx`: platform-admin household creation and membership assignment panel.
- `apps/web/components/admin-smtp-config-form.tsx`: platform admin SMTP config and connectivity-test client form.
- `apps/web/components/admin-settings-form.tsx`: platform admin public/browser base URL client form.
- `apps/web/components/admin-section-nav.tsx`: shared platform-admin section navigation.
- `apps/web/components/household-ai-suggestions.tsx`: household AI suggestion request form and result rendering.
- `apps/web/lib/server-auth.ts`: server-side session and admin data fetching helpers.

## Documentation

- `docs/PROJECT_STATE.md`: latest implementation state, validation results, blockers, and next recommended step.
- `docs/MILESTONES.md`: roadmap.
- `docs/ARCHITECTURE.md`: high-level technical shape.
- `docs/VERSIONING.md`: canonical versioning and planned release/update workflow.
- `docs/DEPLOYMENT.md`: current self-hosted deployment guidance and planned production/LXC path.
- `docs/AI_INTEGRATION.md`: AI provider and suggestion architecture guidance plus delivered foundation notes.
- `docs/DOMAIN_MODEL.md`: initial entity definitions.
- `docs/SECURITY.md`: security posture and guardrails.
- `docs/TEST_STRATEGY.md`: milestone validation policy, command order, and reporting expectations.

## Local-Only

- `private-docs/`: gitignored space for local-only planning notes, private SaaS operations material, internal prompts, and runbooks that should not ship in the public repository.
