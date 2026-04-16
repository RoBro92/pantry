#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [[ -x "${SCRIPT_DIR}/install-pantro.sh" ]]; then
    exec "${SCRIPT_DIR}/install-pantro.sh" "$@"
  fi
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

REPOSITORY="${PANTRO_REPOSITORY:-${PANTRY_REPOSITORY:-RoBro92/pantry}}"
curl -fsSL "https://raw.githubusercontent.com/${REPOSITORY}/main/infra/scripts/install-pantro.sh" -o "${TMP_DIR}/install-pantro.sh"
chmod +x "${TMP_DIR}/install-pantro.sh"
exec "${TMP_DIR}/install-pantro.sh" "$@"
