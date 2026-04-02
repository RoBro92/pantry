# V1 Scope

V1 means the first usable self-hosted release, not the final product vision.

## In Scope

- User accounts and session-based login.
- Household creation and membership management.
- Role enforcement for `platform_admin`, `household_admin`, and `household_user`.
- Location groups and locations.
- Product, barcode, and stock-lot tracking.
- Basic household dashboards and admin shell pages.
- Admin bootstrap CLI and password reset CLI.
- PostgreSQL-backed API with Redis available for worker jobs and rate-limited or queued work.
- Structured logs and audit-event foundations.

## Explicitly Not In Scope For This Initial Scaffold

- Full receipt import implementation.
- Full AI workflows.
- SaaS billing internals.
- Rich email or SMTP management UI.
- Public multi-tenant cloud control plane.

