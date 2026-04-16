#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=infra/scripts/lib/pantro-selfhost.sh
source "${SCRIPT_DIR}/pantro-selfhost.sh"
