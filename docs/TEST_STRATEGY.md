# Test Strategy

## Early Priorities

- Unit tests for domain logic once domain services exist.
- API integration tests for auth, tenant scoping, and critical mutations.
- Worker tests for import and AI job orchestration.
- Web smoke tests for admin shell and key CRUD flows.

## Risk-Based Focus

- Tenant isolation.
- Auth and session behavior.
- Import safety and validation.
- Audit-event creation for sensitive actions.

## Current State

Milestone 1 adds the first API tests:

- Login, current-session, and logout flow.
- Email normalization during authentication.
- Server-side household membership enforcement.

## Current Commands

```bash
python3 -m pip install -r apps/api/requirements-dev.txt
cd apps/api && pytest
npm run typecheck:web
npm run build:web
```
