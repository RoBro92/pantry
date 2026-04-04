#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="$(tr -d '[:space:]' < "${ROOT_DIR}/VERSION")"
IMAGE_NAMESPACE="${PANTRY_IMAGE_NAMESPACE:-ghcr.io/example}"
RELEASE_REPOSITORY="${RELEASE_CHECK_REPOSITORY:-}"

printf 'VERSION=%s\n' "${VERSION}"
printf 'RELEASE_TAG=v%s\n' "${VERSION}"
printf 'WEB_IMAGE=%s/pantry-web:%s\n' "${IMAGE_NAMESPACE}" "${VERSION}"
printf 'API_IMAGE=%s/pantry-api:%s\n' "${IMAGE_NAMESPACE}" "${VERSION}"
printf 'WORKER_IMAGE=%s/pantry-worker:%s\n' "${IMAGE_NAMESPACE}" "${VERSION}"

if [[ -n "${RELEASE_REPOSITORY}" ]]; then
  printf 'RELEASE_METADATA_URL=https://api.github.com/repos/%s/releases/latest\n' "${RELEASE_REPOSITORY}"
  printf 'RELEASES_PAGE_URL=https://github.com/%s/releases\n' "${RELEASE_REPOSITORY}"
fi
