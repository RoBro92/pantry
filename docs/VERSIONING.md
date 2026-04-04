# Versioning

## Source Of Truth

- The repository root `VERSION` file is the authoritative application version.
- Runtime defaults for API and worker read `VERSION` directly when `APP_VERSION` is not provided.
- Web builds and dev commands inject `NEXT_PUBLIC_APP_VERSION` from `VERSION`.

## Current Implemented Usage

- Docker Compose injects `APP_VERSION` and `NEXT_PUBLIC_APP_VERSION` into the API, worker, and web services.
- Root web scripts export `NEXT_PUBLIC_APP_VERSION` from `VERSION` before host-side `dev`, `build`, and `typecheck` commands run.
- Structured API and worker logs bind the running version in log context by default.
- The current version is exposed through:
  - the landing page
  - the authenticated app shell sidebar
  - the admin overview update card
  - `GET /api/health`
  - admin diagnostics

## Update-Check Foundation

- Pantry includes an advisory, read-only update check for platform admins.
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

- `RELEASE_CHECK_REPOSITORY`
- `RELEASE_CHECK_METADATA_URL`
- `RELEASE_CHECK_TIMEOUT_SECONDS`

Relevant admin and API surfaces:

- `GET /api/platform-admin/release-status`
- `GET /api/platform-admin/diagnostics`
- `/admin`
- `/admin/diagnostics`

## Recommended Release Flow

The recommended maintainer release flow is:

1. Validate `main` with `./infra/scripts/validate-release.sh`.
2. Bump `VERSION` with `./infra/scripts/bump-version.sh X.Y.Z`.
3. Commit the release prep on `main`.
4. Create the annotated tag with `./infra/scripts/tag-release.sh X.Y.Z`.
5. Push `main` and `vX.Y.Z`.
6. Let `.github/workflows/release.yml` publish versioned GHCR images and create or update the GitHub Release.
7. Let Pantry compare its current version to GitHub Release metadata and show an update-available notice to platform admins.
8. Let the operator update deployment manifests manually.

Supporting repo automation:

- `.github/workflows/release.yml`
- `infra/scripts/validate-release.sh`
- `infra/scripts/bump-version.sh`
- `infra/scripts/tag-release.sh`
- `infra/scripts/release-manifest.sh`
- `infra/scripts/check-release-metadata.sh`
- `infra/docker/*.production.Dockerfile`

## Recommended Artifact Shape

- Git tag: `vX.Y.Z`
- GitHub Release: `vX.Y.Z`
- GHCR image tags:
  - `ghcr.io/<owner>/pantry-web:X.Y.Z`
  - `ghcr.io/<owner>/pantry-api:X.Y.Z`
  - `ghcr.io/<owner>/pantry-worker:X.Y.Z`

This keeps `PANTRY_VERSION=X.Y.Z` usable both as the runtime version and the pinned deployment image tag, while Git tags and GitHub Releases continue to use `vX.Y.Z`.

## Public Self-Hosted Assets

The public self-hosted assets live in GitHub, not GHCR:

- `infra/compose/pantry.yml`
- `infra/env/pantry.env.example`
- `infra/scripts/install-pantry.sh`
- `infra/scripts/update-pantry.sh`
- `infra/scripts/healthcheck-pantry.sh`

GHCR is only the image source.

## GitHub Release Integration

- `release-manifest.sh` prints the expected tag, image references, and Releases metadata URL.
- `check-release-metadata.sh` queries GitHub Releases latest metadata from the CLI.
- The release workflow creates the GitHub Release if it does not exist yet and updates the title if it already exists.
- Release notes are generated in GitHub so the installer and advisory update check can point operators at one conventional source of truth.

## Still Not Implemented

- fuller changelog automation beyond GitHub generated notes
- unattended update or rollback tooling

## Version Shape

- Start at `0.1.0`.
- Use semantic-version-like increments.
- Tie database migrations and release notes to versioned changes once persistence begins.
