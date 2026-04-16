#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -x "${SCRIPT_DIR}/healthcheck-pantro.sh" ]]; then
  exec "${SCRIPT_DIR}/healthcheck-pantro.sh" "$@"
fi

REPOSITORY="${PANTRO_REPOSITORY:-${PANTRY_REPOSITORY:-RoBro92/pantry}}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

curl -fsSL "https://raw.githubusercontent.com/${REPOSITORY}/main/infra/scripts/healthcheck-pantro.sh" -o "${TMP_DIR}/healthcheck-pantro.sh"
chmod +x "${TMP_DIR}/healthcheck-pantro.sh"
exec "${TMP_DIR}/healthcheck-pantro.sh" "$@"
