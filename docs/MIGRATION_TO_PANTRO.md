# Migration To Pantro

This repository now treats `Pantro` as the canonical product and release name.

## Canonical Names

- Repo-root development helper: `./pantro`
- Self-host installer/update/healthcheck scripts: `install-pantro.sh`, `update-pantro.sh`, `healthcheck-pantro.sh`
- Released compose and env assets: `pantro.yml`, `pantro.env.example`
- GHCR images: `pantro-web`, `pantro-api`, `pantro-worker`
- Environment prefixes for the new self-hosted and local-bootstrap surfaces: `PANTRO_*`
- Workspace/package names: `pantro`, `@pantro/web`, `@pantro/shared-types`

## Compatibility Aliases

The migration keeps the old Pantry names temporarily where existing installs depend on them:

- `./pantry` still forwards to `./pantro`
- `install-pantry.sh`, `update-pantry.sh`, and `healthcheck-pantry.sh` still forward to the Pantro scripts
- `pantry.yml` and `pantry.env.example` are still shipped as upgrade-safe aliases for existing installs
- `PANTRY_*` local-bootstrap env names are still accepted, but `PANTRO_*` is now canonical
- GHCR still publishes `pantry-web`, `pantry-api`, and `pantry-worker` tags alongside the new `pantro-*` names for this release line

## Existing Installs

- Existing installs can remain in `/opt/pantry` and `/srv/pantry`; new installs default to `/opt/pantro` and `/srv/pantro`
- Existing Pantry-named compose/env/script paths continue to work during the migration window
- New installs write both Pantro and Pantry self-hosted path variables into `.env` so the canonical files and legacy aliases stay consistent

## Operator Guidance

- Prefer the Pantro names in all new docs, automation, and examples
- If you are upgrading an existing Pantry install, you can use the legacy Pantry aliases for the upgrade and move to the Pantro names afterward
- Treat the legacy Pantry names as transitional compatibility only, not the long-term canonical interface
