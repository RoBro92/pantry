#!/usr/bin/env bash
set -euo pipefail

COMPOSE_CMD="${COMPOSE_CMD:-docker compose}"
read -r -a COMPOSE_ARGS <<<"${COMPOSE_CMD}"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Usage: e2e-seed.sh

Seeds stable Playwright/E2E data through the running API container and prints the JSON manifest.

Environment:
  COMPOSE_CMD  Compose command for the running local stack. Default: docker compose
EOF
  exit 0
fi

command -v "${COMPOSE_ARGS[0]}" >/dev/null 2>&1 || {
  echo "Missing required command: ${COMPOSE_ARGS[0]}" >&2
  exit 1
}

"${COMPOSE_ARGS[@]}" exec -T api python -m app.cli seed-e2e --json | tail -n 1
