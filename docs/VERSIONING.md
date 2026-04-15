# Versioning

Pantry keeps release visibility explicit and operator-controlled.

## Running Version

- The repository `VERSION` file is the source of truth for the application version
- The running stack surfaces that version in diagnostics and update related UI

## Release Source Of Truth

- GitHub Releases provide the primary public release metadata
- A release may also include a `release.json` asset for structured metadata
- GHCR is used for image distribution

## Update Model

- Pantry does not auto update
- Operators pull new images, run migrations, restart services, and verify health deliberately
- The bundled update script automates that operator workflow without turning it into background self update behavior

For the public release and upgrade checklist, see [docs/RELEASE_RUNBOOK.md](RELEASE_RUNBOOK.md).

## Compatibility

- Release assets, container tags, and the `VERSION` file should stay aligned
- Restore compatibility is stricter than normal upgrade compatibility and depends on the backup format and schema support in the running build
