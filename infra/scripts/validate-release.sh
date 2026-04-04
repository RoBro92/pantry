#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="$(tr -d '[:space:]' < "${ROOT_DIR}/VERSION")"

printf '==> VERSION\n'
"${ROOT_DIR}/infra/scripts/read-version.sh"

printf '==> Shell syntax\n'
bash -n \
  "${ROOT_DIR}/infra/scripts/read-version.sh" \
  "${ROOT_DIR}/infra/scripts/release-manifest.sh" \
  "${ROOT_DIR}/infra/scripts/check-release-metadata.sh" \
  "${ROOT_DIR}/infra/scripts/install-pantry.sh" \
  "${ROOT_DIR}/infra/scripts/update-pantry.sh" \
  "${ROOT_DIR}/infra/scripts/healthcheck-pantry.sh" \
  "${ROOT_DIR}/infra/scripts/lib/pantry-selfhost.sh" \
  "${ROOT_DIR}/infra/scripts/validate-release.sh" \
  "${ROOT_DIR}/infra/scripts/bump-version.sh" \
  "${ROOT_DIR}/infra/scripts/tag-release.sh"

printf '==> Release manifest\n'
"${ROOT_DIR}/infra/scripts/release-manifest.sh"

printf '==> API release tests\n'
(
  cd "${ROOT_DIR}/apps/api"
  pytest tests/test_release_updates.py tests/test_platform_admin_api.py -q
)

printf '==> Compose render\n'
docker compose --env-file "${ROOT_DIR}/infra/env/pantry.env.example" -f "${ROOT_DIR}/infra/compose/pantry.yml" config >/dev/null

printf '==> Production image builds\n'
docker build -f "${ROOT_DIR}/infra/docker/api.production.Dockerfile" -t pantry-api-production:validate "${ROOT_DIR}" >/dev/null
docker build -f "${ROOT_DIR}/infra/docker/worker.production.Dockerfile" -t pantry-worker-production:validate "${ROOT_DIR}" >/dev/null
docker build \
  -f "${ROOT_DIR}/infra/docker/web.production.Dockerfile" \
  --build-arg NEXT_PUBLIC_APP_VERSION="${VERSION}" \
  -t pantry-web-production:validate \
  "${ROOT_DIR}" >/dev/null

printf '==> Release validation complete\n'
