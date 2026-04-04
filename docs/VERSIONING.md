# Versioning

## Source Of Truth

- The repository root `VERSION` file is the authoritative application version.
- Runtime defaults for API and worker now read `VERSION` directly when `APP_VERSION` is not provided.
- Web builds and dev commands inject `NEXT_PUBLIC_APP_VERSION` from `VERSION`; the frontend no longer hardcodes a real release version fallback.

## Current Implemented Usage

- Docker Compose injects `APP_VERSION` and `NEXT_PUBLIC_APP_VERSION` from `VERSION` for the API, worker, and web services.
- Root web scripts now export `NEXT_PUBLIC_APP_VERSION` from `VERSION` before host-side `dev`, `build`, and `typecheck` commands run.
- Structured API and worker logs now bind the running version in log context by default.
- The current version is exposed through:
  - the landing page
  - the authenticated app shell sidebar
  - the admin overview update card
  - `GET /api/health`
  - admin diagnostics
- Documentation and release notes should reference `VERSION`, not duplicate their own canonical version value.

## Update-Check Foundation

- Pantry now includes an advisory, read-only update check for platform admins.
- The update source is GitHub Releases latest-release metadata.
- The update check is server-owned in the API layer and does not rely on browser-side scraping.
- The update check shows:
  - current version
  - latest available version
  - whether an update is available
  - release tag
  - release notes URL when available
- The update check fails gracefully when metadata is unavailable or not configured.
- Pantry does not auto-download, auto-apply, or auto-restart updates.

Relevant environment variables:

- `RELEASE_CHECK_REPOSITORY`: `owner/repo` used to call GitHub Releases latest metadata
- `RELEASE_CHECK_METADATA_URL`: optional override for the latest-release metadata endpoint
- `RELEASE_CHECK_TIMEOUT_SECONDS`: timeout for the advisory metadata request

Relevant admin/API surfaces:

- `GET /api/platform-admin/release-status`
- `GET /api/platform-admin/diagnostics`
- `/admin`
- `/admin/diagnostics`

## Recommended Release Flow

The recommended self-hosted release flow is:

1. Validate `main`.
2. Bump `VERSION`.
3. Create a Git tag and GitHub Release for that version.
4. Build and publish versioned runtime images to GHCR.
5. Have Pantry compare its current version to GitHub Release metadata and show an update-available notice to platform admins.
6. Let the operator update deployment manifests manually.

This keeps release publishing centralized while preserving operator control for self-hosted upgrades.

Supporting repo scaffolding in this pass:

- `infra/scripts/release-manifest.sh`
- `infra/scripts/check-release-metadata.sh`
- `infra/github-actions/release.yml.example`
- `infra/docker/*.production.Dockerfile`

## Recommended Artifact Shape

- Git tag: `vX.Y.Z`
- GitHub Release: `vX.Y.Z`
- GHCR image tags:
  - `ghcr.io/<owner>/pantry-web:X.Y.Z`
  - `ghcr.io/<owner>/pantry-api:X.Y.Z`
  - `ghcr.io/<owner>/pantry-worker:X.Y.Z`

This keeps `PANTRY_VERSION=X.Y.Z` usable both as the runtime version and the pinned production image tag, while Git tags and GitHub Releases continue to use `vX.Y.Z`.

## Still Not Implemented

- live GitHub Actions automation for tag, release, and GHCR publication
- fuller changelog automation
- unattended update or rollback tooling

## Version Shape

- Start at `0.1.0`.
- Use semantic-version-like increments.
- Tie database migrations and release notes to versioned changes once persistence begins.
