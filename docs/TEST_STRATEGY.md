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

No formal test harness is added in this scaffold yet. Milestone 1 should add the first API and domain tests alongside the initial persistence layer.

