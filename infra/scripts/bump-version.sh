#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s <x.y.z>\n' "${0##*/}" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_VERSION="$1"

if [[ ! "${TARGET_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z]+)*$ ]]; then
  printf 'Invalid version: %s\n' "${TARGET_VERSION}" >&2
  exit 1
fi

printf '%s\n' "${TARGET_VERSION}" > "${ROOT_DIR}/VERSION"
printf 'Updated VERSION to %s\n' "${TARGET_VERSION}"
printf 'Next steps:\n'
printf '  1. Review git diff and commit VERSION.\n'
printf '  2. Run ./infra/scripts/tag-release.sh %s\n' "${TARGET_VERSION}"
