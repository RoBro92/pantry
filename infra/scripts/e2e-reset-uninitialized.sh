#!/usr/bin/env bash
set -euo pipefail

COMPOSE_CMD="${COMPOSE_CMD:-docker compose}"
read -r -a COMPOSE_ARGS <<<"${COMPOSE_CMD}"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Usage: e2e-reset-uninitialized.sh

Resets application data in the running API container to the first-run setup state for Playwright/E2E.

Environment:
  COMPOSE_CMD  Compose command for the running local stack. Default: docker compose
EOF
  exit 0
fi

command -v "${COMPOSE_ARGS[0]}" >/dev/null 2>&1 || {
  echo "Missing required command: ${COMPOSE_ARGS[0]}" >&2
  exit 1
}

"${COMPOSE_ARGS[@]}" exec -T api python - <<'PY'
from app.core.db import SessionLocal
from app.services.e2e_seed import reset_application_data

with SessionLocal() as db:
    reset_application_data(db)
PY
