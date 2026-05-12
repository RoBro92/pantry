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
(cd apps/api && pytest -q)
./infra/scripts/validate-release.sh
```

The enforced release gate lives in `./infra/scripts/validate-release.sh`. It includes source-stack smoke validation and full Playwright E2E before the existing release-oriented checks continue.

4. Confirm `VERSION` matches the intended release version.
5. Create the release tag with:

```bash
./infra/scripts/tag-release.sh X.Y.Z
git push origin vX.Y.Z
```

6. Verify the `Release Publish` workflow completed successfully. That workflow enforces the release validation gate before publishing images and GitHub Release metadata.
7. Check the released install and update entry points still match the docs:
   `infra/compose/pantro.yml`, `infra/env/pantro.env.example`, `infra/scripts/install-pantro.sh`, `infra/scripts/update-pantro.sh`, and `infra/scripts/healthcheck-pantro.sh`.
8. Keep the compatibility aliases healthy during the migration window:
   `infra/compose/pantry.yml`, `infra/env/pantry.env.example`, `infra/scripts/install-pantry.sh`, `infra/scripts/update-pantry.sh`, and `infra/scripts/healthcheck-pantry.sh`.

## Operator Upgrade Checklist

1. Run `./healthcheck-pantro.sh --install-dir /opt/pantro` before upgrading so rollback starts from a known-good stack.
2. Record the current `PANTRO_VERSION` and keep the existing `.env` plus compose asset backups until post-update validation passes.
3. Back up PostgreSQL data and Pantro-managed import storage before upgrading.
4. Review the new `infra/env/pantro.env.example` before reusing older environment values.
5. Run the explicit operator update flow:

```bash
./update-pantro.sh
```

6. Run the bundled health check:

```bash
./healthcheck-pantro.sh --install-dir /opt/pantro
```

7. Confirm the browser UI, API health endpoint, worker status, and any optional integrations you rely on.
8. Treat restore compatibility as stricter than normal upgrades and verify backup format support before using older backup bundles on a newer build.
9. If your install still uses Pantry-named asset paths, the legacy `update-pantry.sh` and `healthcheck-pantry.sh` aliases remain supported during this migration.

## Notes

- Pantro is self-hosted and operator-managed in this public repository
- Pantro does not auto-update
- AI features remain optional and may require separate provider validation after an upgrade
