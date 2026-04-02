# API Spec

This file records the initial API shape and conventions, not a completed endpoint catalog.

## Current Endpoint

- `GET /api/health`
  - Returns service status, environment, version, and request ID.

## Planned API Conventions

- All household-scoped endpoints resolve tenant access server-side.
- Request and response payloads should use opaque external IDs for tenant-facing objects.
- Mutation endpoints should emit audit events for domain-significant changes.
- Bulk import and AI flows should be asynchronous where latency or safety review makes synchronous APIs inappropriate.

## Near-Term Endpoint Areas

- Auth and session endpoints.
- Household and membership management.
- Location group and location CRUD.
- Product and stock-lot CRUD.
- Admin bootstrap and recovery CLI integration where appropriate.

