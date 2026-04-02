# Auth And Roles

Milestone 1 implements the first auth and role foundation for Pantry.

## Roles

- `platform_admin`: platform-wide administration, deployment oversight, and cross-household support tooling where allowed.
- `household_admin`: manages one household, its members, locations, and household settings.
- `household_user`: standard household member with routine pantry, recipe, and shopping access.

## Implemented Auth Behavior

- Session-based auth for the web app.
- Password-based login as the baseline self-hosted path.
- CLI-based bootstrap for the first platform admin.
- CLI-based password reset for operational recovery.
- Signed cookie sessions backed by server-side user and membership checks on every request.

## Implemented Endpoints

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/session`
- `GET /api/platform-admin/overview`
- `GET /api/platform-admin/users`
- `GET /api/platform-admin/households`

## Enforcement Rules

- Role checks happen server-side.
- Household access is derived from authenticated memberships, not from client-supplied tenant IDs alone.
- Worker jobs processing tenant data must carry explicit tenant context and authorization assumptions.

## CLI Commands

```bash
docker compose run --rm api python -m app.cli bootstrap-platform-admin --email admin@example.com --display-name "Pantry Admin"
docker compose run --rm api python -m app.cli reset-password --email admin@example.com
```

## Relevant Environment Variables

- `SESSION_SECRET_KEY`
- `SESSION_COOKIE_NAME`
- `SESSION_MAX_AGE_SECONDS`
- `SESSION_HTTPS_ONLY`
- `SESSION_SAME_SITE`
