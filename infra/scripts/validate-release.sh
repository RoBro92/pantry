#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="$(tr -d '[:space:]' < "${ROOT_DIR}/VERSION")"
DEV_STACK_STARTED=0

cleanup() {
  if [[ "${DEV_STACK_STARTED}" -eq 1 ]]; then
    printf '==> Shutting down local validation stack\n'
    "${ROOT_DIR}/pantry" stop >/dev/null
  fi
}

trap cleanup EXIT

printf '==> VERSION\n'
"${ROOT_DIR}/infra/scripts/read-version.sh"

printf '==> Node runtime\n'
command -v node >/dev/null
command -v npm >/dev/null
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
NPM_MAJOR="$(npm -v | cut -d. -f1)"
printf 'node=%s npm=%s\n' "$(node -v)" "$(npm -v)"

if [[ "${NODE_MAJOR}" != "20" || "${NPM_MAJOR}" != "10" ]]; then
  echo "Release validation requires Node.js 20.x and npm 10.x for the web and Playwright checks." >&2
  exit 1
fi

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
  "${ROOT_DIR}/infra/scripts/tag-release.sh" \
  "${ROOT_DIR}/infra/scripts/smoke-check.sh" \
  "${ROOT_DIR}/infra/scripts/e2e-seed.sh" \
  "${ROOT_DIR}/infra/scripts/e2e-reset-uninitialized.sh" \
  "${ROOT_DIR}/infra/scripts/worker-once.sh"

printf '==> Release manifest\n'
"${ROOT_DIR}/infra/scripts/release-manifest.sh"

printf '==> API release tests\n'
(
  cd "${ROOT_DIR}/apps/api"
  pytest tests/test_release_updates.py tests/test_platform_admin_api.py -q
)

printf '==> Source-stack smoke and E2E gate\n'
"${ROOT_DIR}/pantry" start --demo >/dev/null
DEV_STACK_STARTED=1
"${ROOT_DIR}/infra/scripts/smoke-check.sh"
(
  cd "${ROOT_DIR}"
  CI=1 npm run test:e2e
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
