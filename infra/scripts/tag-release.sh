#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ $# -gt 1 ]]; then
  printf 'Usage: %s [x.y.z]\n' "${0##*/}" >&2
  exit 1
fi

VERSION="${1:-$(tr -d '[:space:]' < "${ROOT_DIR}/VERSION")}"
TAG="v${VERSION}"

if [[ ! "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z]+)*$ ]]; then
  printf 'Invalid version: %s\n' "${VERSION}" >&2
  exit 1
fi

if [[ "$(tr -d '[:space:]' < "${ROOT_DIR}/VERSION")" != "${VERSION}" ]]; then
  printf 'VERSION does not match %s. Run ./infra/scripts/bump-version.sh first.\n' "${VERSION}" >&2
  exit 1
fi

if ! git -C "${ROOT_DIR}" diff --quiet || ! git -C "${ROOT_DIR}" diff --cached --quiet; then
  printf 'Git working tree is not clean. Commit or stash changes before tagging.\n' >&2
  exit 1
fi

if git -C "${ROOT_DIR}" rev-parse -q --verify "refs/tags/${TAG}" >/dev/null; then
  printf 'Tag %s already exists.\n' "${TAG}" >&2
  exit 1
fi

git -C "${ROOT_DIR}" tag -a "${TAG}" -m "Pantro ${TAG}"
printf 'Created tag %s\n' "${TAG}"
printf 'Push with:\n'
printf '  git push origin main\n'
printf '  git push origin %s\n' "${TAG}"
