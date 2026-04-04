# Decisions

Initial architectural decisions recorded on 2026-04-02.

## Accepted

| ID | Decision | Why |
| --- | --- | --- |
| D-001 | Use a monorepo with `apps/web`, `apps/api`, `apps/worker`, and `packages/shared-types`. | Keeps product and platform changes coordinated while maintaining service separation. |
| D-002 | Build self-hosted first, but keep deployment and docs ready for future SaaS modes. | The first reliable path is a single-stack deployment, but the repo should not dead-end there. |
| D-003 | Use Next.js for web, FastAPI for API, and Python for worker jobs. | Fast iteration, clear service boundaries, and a good fit for future imports and AI-adjacent workflows. |
| D-004 | Use PostgreSQL as the system of record and Redis for transient/background concerns. | Clear separation between durable data and ephemeral coordination. |
| D-005 | Treat uploaded files as hostile input. | Import and attachment flows are a major attack and abuse boundary. |
| D-006 | Start multi-household and role-aware from day one. | Retrofitting tenancy later is costly and risky. |
| D-007 | Use opaque external IDs for tenant-facing entities. | Avoid predictable enumeration and reduce coupling to internal row IDs. |
| D-008 | Keep reverse proxy and TLS external to the app stack. | Simplifies the application boundary and supports varied deployment environments. |
| D-009 | Use structured logging and distinguish system logs from audit/domain events. | Operational diagnostics and business accountability serve different purposes. |
| D-010 | Introduce AI through a provider abstraction layer from the start. | Avoids hard-coding domain logic to a single provider or hosting model. |
| D-011 | Use SQLAlchemy with Alembic for the first persistence and migration layer. | The project needed a clear migration path before identity and tenancy tables were introduced. |
| D-012 | Use signed cookie sessions for the first web auth foundation. | This keeps Milestone 1 simple for self-hosted deployments while preserving a server-side authorization boundary. |
| D-013 | Use Argon2 password hashing. | Password storage should start with a modern memory-hard hash instead of a weaker transitional choice. |
| D-014 | Keep stock lots as the source of truth for pantry totals, and preserve lot identity on whole-lot moves while splitting partial moves. | This keeps aggregate inventory views derivable, mutation behavior auditable, and future import or reconciliation flows aligned with real lot history. |
| D-015 | Resolve recipe ingredient matches deterministically by explicit pantry-product link first, then by normalized product or alias name. | This keeps recipe coverage predictable, explainable, and safe to enforce server-side across tenants. |
| D-016 | Calculate recipe coverage in ingredient order and derive shopping gaps from the remaining pantry quantity for each mapped product. | This avoids double-counting shared pantry stock when the same product appears in multiple ingredient lines. |
| D-017 | Persist recipe URL import capture records before implementing parsing or scraping. | This gives v1 a clean route/model/service boundary for later worker-backed URL import processing without overbuilding the parser now. |
| D-018 | Keep the pantry import pipeline review-first, with explicit import confirmation as the only stock-write path. | This preserves human oversight, keeps hostile-upload handling isolated from inventory mutation, and lets deterministic/manual ingestion work now while richer parsers plug in later. |
| D-019 | Start AI provider persistence at installation scope, but shape it for future household overrides. | Self-hosted v1 only needs a single configured provider, but household overrides should not require route or storage redesign later. |
| D-020 | Keep AI suggestions advisory-only and read-only in the first AI milestone. | This preserves pantry and import safety while structured prompts, provider health handling, and UI feedback mature. |
| D-021 | Store installation-scoped public/browser URL and SMTP foundation settings in a single instance-settings record, while allowing deployment environment variables to override them. | Self-hosted installs need editable platform settings, but env overrides remain important for immutable deployments and secret injection. |
| D-022 | Keep platform diagnostics on a real-data-only policy backed by app process data, DB queries, Redis checks, and worker heartbeats instead of guessed host metrics. | Honest self-hosted diagnostics are more trustworthy than simulated CPU, memory, or container metrics the app cannot directly observe. |
| D-023 | Normalize deployment modes to `self_hosted`, `demo`, and `saas`, with `saas` remaining a placeholder boundary in the public repo. | This keeps mode handling simple in config and shared types without exposing hosted tiering in the public UI. |
| D-024 | Introduce `FeatureFlag` and `UsageCounter` models before SaaS logic exists, but keep quota checks non-enforcing for now. | The structural primitives are needed early so future hosted work does not require invasive rewrites, while self-hosted behavior stays unchanged today. |
| D-025 | Remove internal prompt and Codex-specific instructions from the public repository and keep them only in local `private-docs/`. | Public docs should remain user-relevant and open-source-safe, while internal workflows and private operational notes stay out of versioned public history. |
| D-026 | Add a one-time browser-based setup flow for the first platform admin instead of relying only on CLI bootstrap. | A real self-hosted first-run experience needs an in-product path from fresh install to usable admin console without exposing repeated bootstrap once initialization is complete. |
| D-027 | Restrict pantry structure creation to `household_admin` while leaving stock add/move/remove available to `household_user`. | Household structure changes are effectively tenant configuration, while routine stock handling should remain available to day-to-day household members. |
| D-028 | Keep `VERSION` as the single release/version source of truth across runtime services, published artifacts, and operator-facing version display. | This avoids version drift between docs, UI, API responses, and release artifacts. |
| D-029 | Keep the self-hosted update path operator-driven, using GitHub Releases metadata and GHCR images rather than unattended in-app auto-updates. | Self-hosted operators should control upgrade timing and rollback decisions explicitly. |
| D-030 | Keep release-metadata fetching and update-available logic in the API layer, and ship production deployment assets that pin image versions explicitly. | This keeps admin UI simple, avoids browser-side scraping, and preserves deliberate operator-controlled upgrades on self-hosted installs. |
| D-031 | Keep public self-hosted deployment assets and helper scripts in the GitHub repo, while GHCR remains image-only. | This keeps install and update mechanics conventional for a Docker application and avoids turning GHCR into a metadata or script distribution channel. |

## Deferred

- The exact migration tool and ORM/query strategy.
- The exact session/auth implementation choice.
- The exact file storage backend for uploads in hosted deployments.
- The exact QR-code library and rendering location.
