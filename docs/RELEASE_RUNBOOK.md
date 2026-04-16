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

The enforced release gate now lives in `./infra/scripts/validate-release.sh`. It includes source-stack smoke validation and full Playwright E2E before the existing release-oriented checks continue.

4. Confirm `VERSION` matches the intended release version.
5. Create the release tag with:

```bash
./infra/scripts/tag-release.sh X.Y.Z
git push origin vX.Y.Z
```

6. Verify the `Release Publish` workflow completed successfully. That workflow now enforces the release validation gate, including smoke validation and Playwright E2E, before publishing images and GitHub Release metadata.
7. Check the released install and update entry points still match the docs:
   `infra/compose/pantry.yml`, `infra/env/pantry.env.example`, `infra/scripts/install-pantry.sh`, `infra/scripts/update-pantry.sh`, and `infra/scripts/healthcheck-pantry.sh`.

## Operator Upgrade Checklist

1. Back up PostgreSQL data and Pantro-managed upload storage before upgrading.
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

- Pantro is self-hosted and operator-managed in this public repository
- Pantro does not auto-update
- AI features remain optional and may require separate provider validation after an upgrade
