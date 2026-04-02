# Deployment Modes

Pantry is structured so one codebase can support several deployment modes over time.

## `self_hosted`

- Primary mode today.
- One stack owned by the operator.
- Public repo includes setup and operational guidance for this mode.
- Reverse proxy and TLS are external responsibilities.

## `demo`

- Temporary showcase environment.
- Data may be disposable or periodically reset.
- Restricted integrations and minimal secrets footprint.
- Useful for previews without exposing private SaaS operations.

## `saas_free`

- Future hosted tier with constrained limits and feature gating.
- Requires `FeatureFlag` and `UsageCounter` support.
- Operational specifics belong in local-only `private-docs/`.

## `saas_supporter`

- Future hosted paid/supporter tier.
- Likely includes higher usage limits, premium features, and support workflows.
- Billing and support mechanics are intentionally not implemented in this repo pass.

