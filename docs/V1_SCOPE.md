# V1 Scope

V1 means the first usable self-hosted release, not the final product vision.

## In Scope

- User accounts and session-based login.
- Browser-based first-run setup for the initial platform admin.
- Household creation and membership management.
- Role enforcement for `platform_admin`, `household_admin`, and `household_user`.
- Location groups and locations.
- Product, barcode, and stock-lot tracking.
- Manual recipe entry, ingredient mapping, pantry coverage, and shopping-gap calculation.
- Recipe URL import capture foundation for later parsing work.
- Shopping workflows that turn pantry and recipe gaps into actionable household lists.
- Basic household dashboards and admin shell pages.
- Installation-console flows for creating users, creating households, and assigning memberships.
- Platform admin diagnostics, public/browser base URL management, and SMTP readiness foundation.
- Current-version visibility in the UI and diagnostics, plus an admin-facing update-available notice before release.
- Versioned self-hosted release flow using `VERSION`, GitHub Releases, and published container images.
- Production deployment guidance for Docker-based self-hosting, including the planned LXC cluster target.
- Pantry location QR/browser deep links that still require authenticated household access.
- Admin bootstrap CLI and password reset CLI.
- PostgreSQL-backed API with Redis available for worker jobs and rate-limited or queued work.
- Structured logs and audit-event foundations.

## Explicitly Not In Scope For This Initial Scaffold

- Full receipt import implementation.
- Shopping-list persistence and workflow automation.
- Full AI workflows.
- SaaS billing internals.
- Auto-updating deployments or unattended in-app upgrades.
- Full notification, invite, or campaign email workflows.
- Public multi-tenant cloud control plane.
