# API Spec

This file records the initial API shape and conventions, not a completed endpoint catalog.

## Current Endpoints

- `GET /api/health`
  - Returns service status, environment, version, and request ID.
- `POST /api/auth/login`
  - Authenticates a user and establishes a signed session cookie.
- `POST /api/auth/logout`
  - Clears the current signed session.
- `GET /api/auth/session`
  - Returns the current authenticated user and active household memberships.
- `GET /api/platform-admin/overview`
  - Returns installation-level counts for platform admins.
- `GET /api/platform-admin/users`
  - Returns user summaries for the platform admin shell.
- `GET /api/platform-admin/households`
  - Returns household summaries for the platform admin shell.
- `GET /api/platform-admin/ai/provider-config`
  - Returns the instance-scoped AI provider configuration summary with secrets redacted.
- `PUT /api/platform-admin/ai/provider-config`
  - Creates or updates the instance-scoped AI provider configuration and emits an audit event.
- `POST /api/platform-admin/ai/provider-config/health-check`
  - Checks the configured provider, updates health metadata, and returns discovered models when available.
- `GET /api/households/{household_external_id}`
  - Returns a household summary only if server-side membership or platform admin access resolves successfully.
- `GET /api/households/{household_external_id}/pantry/overview`
  - Returns household pantry reference data, aggregated product totals derived from stock lots, filtered stock lots, and recent pantry audit activity.
- `GET /api/households/{household_external_id}/pantry/near-expiry`
  - Returns active stock lots expiring within a caller-selected window.
- `POST /api/households/{household_external_id}/location-groups`
  - Creates a household location group and emits an audit event.
- `POST /api/households/{household_external_id}/locations`
  - Creates a household location inside an existing group and emits an audit event.
- `POST /api/households/{household_external_id}/products`
  - Creates a product with deterministic alias and barcode normalization and emits an audit event.
- `POST /api/households/{household_external_id}/stock-lots`
  - Creates a new stock lot and emits an audit event.
- `POST /api/households/{household_external_id}/stock-lots/{lot_external_id}/remove`
  - Removes quantity from a lot, depletes the lot when quantity reaches zero, and emits an audit event.
- `POST /api/households/{household_external_id}/stock-lots/{lot_external_id}/move`
  - Moves stock to another location, preserving lot identity for full moves and splitting partial moves into a new lot.
- `GET /api/households/{household_external_id}/recipes`
  - Returns household recipes with recipe-level pantry coverage summaries and shopping-gap counts.
- `GET /api/households/{household_external_id}/recipes/{recipe_external_id}`
  - Returns recipe detail, ingredient coverage, linked pantry products, and derived shopping gaps.
- `POST /api/households/{household_external_id}/recipes`
  - Creates a manual household recipe, resolves deterministic ingredient-to-product matches, and emits an audit event.
- `PUT /api/households/{household_external_id}/recipes/{recipe_external_id}`
  - Replaces recipe title, notes, and ingredient lines, recomputes deterministic links, and emits an audit event.
- `POST /api/households/{household_external_id}/recipe-imports/url`
  - Captures a normalized recipe URL import request as v1 foundation work and emits an audit event.
- `GET /api/households/{household_external_id}/imports`
  - Returns household import history with job status, review counts, and source-file summaries.
- `GET /api/households/{household_external_id}/imports/{import_external_id}`
  - Returns import detail with source-file metadata, parsed lines, review state, and confirmation readiness.
- `POST /api/households/{household_external_id}/imports/uploads`
  - Stores an upload outside web-served paths, validates size/type, creates an `ImportJob`, and queues worker processing.
- `PUT /api/households/{household_external_id}/imports/{import_external_id}/lines/{line_external_id}`
  - Updates a parsed import line, re-resolves deterministic matching, and records import review audit activity.
- `POST /api/households/{household_external_id}/imports/{import_external_id}/confirm`
  - Confirms a reviewed import and creates pantry stock lots from matched lines only.
- `GET /api/households/{household_external_id}/ai/status`
  - Returns household AI feature availability, resolved provider metadata, and clean unconfigured or unhealthy reasons.
- `POST /api/households/{household_external_id}/ai/suggestions`
  - Generates read-only structured pantry-aware suggestions through the provider abstraction and never mutates pantry, recipe, or import state.

## Planned API Conventions

- All household-scoped endpoints resolve tenant access server-side.
- Request and response payloads should use opaque external IDs for tenant-facing objects.
- Mutation endpoints should emit audit events for domain-significant changes.
- Recipe coverage and shopping-gap calculations should stay deterministic and server-derived from pantry state.
- Bulk import and AI flows should be asynchronous where latency or safety review makes synchronous APIs inappropriate.
- Import endpoints must never write pantry stock before explicit confirmation of reviewed lines.
- AI endpoints should use structured request and response contracts instead of ad hoc prompt strings or free-form markdown output.

## Auth Assumptions

- The current auth foundation uses a signed cookie session rather than a database-backed session table.
- Authorization always resolves the current user and memberships server-side before role checks or household access.

## Next Endpoint Areas

- Household create/update flows for platform admins or household admins as product requirements sharpen.
- Edit and archive flows for pantry structure records.
- Shopping-list persistence and consumption/replenishment workflows.
- Recipe URL import worker execution tied into the new import-job architecture.
- AI-assisted import review flows that reuse the provider abstraction without bypassing human confirmation.
- Household-scoped provider overrides once product requirements justify them.
