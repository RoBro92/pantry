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

## Planned API Conventions

- All household-scoped endpoints resolve tenant access server-side.
- Request and response payloads should use opaque external IDs for tenant-facing objects.
- Mutation endpoints should emit audit events for domain-significant changes.
- Bulk import and AI flows should be asynchronous where latency or safety review makes synchronous APIs inappropriate.

## Auth Assumptions

- The current auth foundation uses a signed cookie session rather than a database-backed session table.
- Authorization always resolves the current user and memberships server-side before role checks or household access.

## Next Endpoint Areas

- Household create/update flows for platform admins or household admins as product requirements sharpen.
- Location group and location CRUD.
- Product and stock-lot CRUD.
- Audit event writes around identity and inventory mutations.
