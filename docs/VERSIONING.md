# Versioning

Pantry keeps version visibility operator-controlled and self-hosted-first.

## Running Version

- The running application version comes from the repository `VERSION` file.
- The app surfaces that version in diagnostics, the admin console, and the updates page.

## Release Metadata Source Of Truth

- Primary source: GitHub Releases latest metadata
- Optional enrichment: a `release.json` asset attached to a GitHub Release
- GHCR: image distribution only

Pantry does not treat GHCR as a release metadata source. If container images exist but no GitHub Release exists, the UI shows a friendly metadata-unavailable state instead of a broken failure.

## Changelog Visibility

- Pantry reads published release notes from the GitHub Release body by default.
- If a `release.json` asset is present, Pantry can use it to enrich summaries, breaking change notes, and manual operator commands.
- Platform admins are prompted once to review current-version notes after an update.

## Updates

- Updates remain advisory only.
- Pantry does not auto-update and does not self-update.
- Operators still pull images, run migrations, and restart services deliberately.
