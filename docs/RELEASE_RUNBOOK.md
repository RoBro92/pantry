# Release Runbook

Concise public checklist for maintainers publishing a release and operators applying one.

## Maintainer Release Checklist

1. Confirm the change is landing through the normal branch and pull-request workflow.
2. Make sure public docs match the shipped self-hosted product scope:
   self-hosted, operator-managed, optional AI, no SaaS logic, and no auto-update.
3. Run the relevant validation for the release:

```bash
npm run typecheck:web
npm run build:web
cd apps/api && pytest -q
docker compose --env-file infra/env/pantry.env.example -f infra/compose/pantry.yml config
./infra/scripts/validate-release.sh
```

4. Confirm `VERSION` matches the intended release version.
5. Create the release tag with:

```bash
./infra/scripts/tag-release.sh X.Y.Z
git push origin vX.Y.Z
```

6. Verify the `Release Publish` workflow completed successfully and published the expected GHCR images and GitHub Release metadata.
7. Check the released install and update entry points still match the docs:
   `infra/compose/pantry.yml`, `infra/env/pantry.env.example`, `infra/scripts/install-pantry.sh`, `infra/scripts/update-pantry.sh`, and `infra/scripts/healthcheck-pantry.sh`.

## Operator Upgrade Checklist

1. Back up PostgreSQL data and Pantry-managed upload storage before upgrading.
2. Review the new `infra/env/pantry.env.example` before reusing older environment values.
3. Run the explicit operator update flow:

```bash
./update-pantry.sh
```

4. Run the bundled health check:

```bash
./healthcheck-pantry.sh --install-dir /opt/pantry
```

5. Confirm the browser UI, API health endpoint, worker status, and any optional integrations you rely on.
6. Treat restore compatibility as stricter than normal upgrades and verify backup format support before using older backup bundles on a newer build.

## Notes

- Pantry is self-hosted and operator-managed in this public repository
- Pantry does not auto-update
- AI features remain optional and may require separate provider validation after an upgrade
