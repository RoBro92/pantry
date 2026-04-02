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

## Planned API Conventions

- All household-scoped endpoints resolve tenant access server-side.
- Request and response payloads should use opaque external IDs for tenant-facing objects.
- Mutation endpoints should emit audit events for domain-significant changes.
- Recipe coverage and shopping-gap calculations should stay deterministic and server-derived from pantry state.
- Bulk import and AI flows should be asynchronous where latency or safety review makes synchronous APIs inappropriate.

## Auth Assumptions

- The current auth foundation uses a signed cookie session rather than a database-backed session table.
- Authorization always resolves the current user and memberships server-side before role checks or household access.

## Next Endpoint Areas

- Household create/update flows for platform admins or household admins as product requirements sharpen.
- Edit and archive flows for pantry structure records.
- Shopping-list persistence and consumption/replenishment workflows.
- Deeper recipe URL parsing and worker-backed import execution.
