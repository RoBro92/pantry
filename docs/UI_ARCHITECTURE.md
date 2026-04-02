# UI Architecture

## Current Structure

- Next.js App Router foundation.
- Root landing page used as a minimal status page.
- Route group reserved for future authenticated or domain pages.
- Shared constants imported from `packages/shared-types`.

## Frontend Rules

- Keep business logic out of purely presentational components.
- Preserve clean separation between layout, route concerns, and future domain modules.
- Keep the UI easy to redesign later by avoiding tightly coupled component logic.
- Prefer server-safe data flow patterns that do not assume client trust.

## Near-Term Expansion

- Auth shell and admin pages.
- Household switcher and tenant-aware navigation.
- Basic CRUD forms for users, households, memberships, and roles.

