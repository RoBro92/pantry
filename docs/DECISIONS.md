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

## Deferred

- The exact migration tool and ORM/query strategy.
- The exact session/auth implementation choice.
- The exact file storage backend for uploads in hosted deployments.
- The exact QR-code library and rendering location.
