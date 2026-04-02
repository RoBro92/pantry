# Auth And Roles

Auth is not implemented in this scaffold, but the target model is defined now so later code lands against an explicit contract.

## Roles

- `platform_admin`: platform-wide administration, deployment oversight, and cross-household support tooling where allowed.
- `household_admin`: manages one household, its members, locations, and household settings.
- `household_user`: standard household member with routine pantry, recipe, and shopping access.

## Planned Auth Behavior

- Session-based auth for the web app.
- Password-based login as the baseline self-hosted path.
- CLI-based bootstrap for the first platform admin.
- CLI-based password reset for operational recovery.

## Enforcement Rules

- Role checks happen server-side.
- Household access is derived from authenticated memberships, not from client-supplied tenant IDs alone.
- Worker jobs processing tenant data must carry explicit tenant context and authorization assumptions.

