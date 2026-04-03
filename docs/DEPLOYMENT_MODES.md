# Deployment Modes

Pantry now validates three deployment modes in shared types and server config:

- `self_hosted`
- `demo`
- `saas`

These modes are boundary markers, not separate public product variants.

## `self_hosted`

- Primary mode today.
- One stack owned by the operator.
- Public repo includes setup, validation, and operational guidance for this mode.
- No hosted-only plan logic, billing flows, or support tooling are exposed here.

## `demo`

- Showcase mode with configuration support only.
- `DEMO_MODE_ENABLED` can be set without changing product behavior outside configuration and diagnostics surfaces.
- No automatic reset system, seeded preview orchestration, or disposable-data lifecycle is implemented yet.

## `saas`

- Placeholder boundary for future hosted work.
- Exists so deployment-mode branching, feature-flag defaults, and usage metering do not require structural rewrites later.
- SaaS business logic, billing, support operations, tenant lifecycle tooling, and hosted-only runbooks remain intentionally out of this repo.

## Separation Strategy

- Shared product logic stays in the public repo only when it is valid for self-hosted and future hosted use.
- Deployment-mode defaults, feature flags, and usage counters live server-side in the API and are enforced there, not in the UI.
- Private hosted operations, billing mechanics, and internal runbooks belong in local-only `private-docs/` or a future private SaaS repository.
- The web UI must not advertise hosted-only concepts while Pantry is operating in self-hosted mode.

## What Exists Now

- Validated deployment-mode config in the API and shared TypeScript package.
- Server-side `FeatureFlag` defaults plus scoped override storage for instance and household use.
- `UsageCounter` storage and request metering foundations with placeholder quota checks that do not enforce limits yet.
- Demo-mode configuration support without demo-specific automation.

## Intentionally Not Implemented

- Billing, subscription plans, or entitlement UX.
- Hosted AI routing or provider logic separate from the existing provider abstraction.
- Demo reset jobs, scheduled wipes, or public demo tenants.
- SaaS-only admin screens, onboarding, or support workflows.
