# Versioning

`VERSION` at the repository root is Pantry’s single source of truth for the application version.

## Release Shape

- Git tags use `vX.Y.Z`
- Container images use `X.Y.Z`
- Self-hosted installs set `PANTRY_VERSION=X.Y.Z`

This keeps the running version, published images, and operator-selected deployment version aligned.

## How Version Data Is Used

- The web app displays the running version
- API health includes the running version
- API and worker processes receive version data from `VERSION` or environment variables derived from it
- Released deployment assets expect `PANTRY_VERSION` to match the image tag being pulled

## Update Model

- Pantry does not auto-update
- Operators choose when to move to a new release
- Updates pull a selected version, run migrations, and restart services explicitly

## Maintainer Release Flow

```bash
./infra/scripts/validate-release.sh
./infra/scripts/bump-version.sh X.Y.Z
./infra/scripts/tag-release.sh X.Y.Z
```

Pushing the tag triggers [release.yml](/Users/robinbrown/Documents/GitHub/pantry/.github/workflows/release.yml), which publishes versioned GHCR images and creates or updates the GitHub Release.
