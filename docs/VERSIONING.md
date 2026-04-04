# Versioning

## Source Of Truth

- The repository root `VERSION` file is the authoritative application version.

## Current Implemented Usage

- Docker Compose injects `APP_VERSION` and `NEXT_PUBLIC_APP_VERSION` from `VERSION` for the API, worker, and web services.
- Root web scripts now export `NEXT_PUBLIC_APP_VERSION` from `VERSION` before host-side `dev`, `build`, and `typecheck` commands run.
- The current version is exposed through:
  - the landing page
  - the authenticated app shell sidebar
  - `GET /api/health`
  - admin diagnostics
- Documentation and release notes should reference `VERSION`, not duplicate their own canonical version value.

## Recommended Release Flow

The recommended self-hosted release flow is:

1. Validate `main`.
2. Bump `VERSION`.
3. Create a Git tag and GitHub Release for that version.
4. Build and publish versioned runtime images to GHCR.
5. Have Pantry compare its current version to GitHub Release metadata and show an update-available notice to platform admins.
6. Let the operator update deployment manifests manually.

This keeps release publishing centralized while preserving operator control for self-hosted upgrades.

## Recommended Artifact Shape

- Git tag: `vX.Y.Z`
- GitHub Release: `vX.Y.Z`
- GHCR image tags:
  - `ghcr.io/<owner>/pantry-web:vX.Y.Z`
  - `ghcr.io/<owner>/pantry-api:vX.Y.Z`
  - `ghcr.io/<owner>/pantry-worker:vX.Y.Z`

Exact repository names and automation details can be finalized in the release milestone, but the version source should remain the root `VERSION` file.

## Planned But Not Implemented Yet

- GitHub Actions or equivalent automation for tag, release, and GHCR publication
- admin-facing update-available notification
- latest-release metadata fetch and comparison logic
- fuller changelog automation
- unattended update or rollback tooling

## Version Shape

- Start at `0.1.0`.
- Use semantic-version-like increments.
- Tie database migrations and release notes to versioned changes once persistence begins.
