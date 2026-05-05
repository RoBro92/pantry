#!/usr/bin/env bash
set -euo pipefail

COMPOSE_CMD="${COMPOSE_CMD:-docker compose}"
read -r -a COMPOSE_ARGS <<<"${COMPOSE_CMD}"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Usage: worker-once.sh

Processes one import or recipe URL job through the running API container. Used by Playwright/E2E helpers.

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
from app.services.import_processing import process_next_import_job
from app.services.recipe_url_imports import process_next_recipe_url_import

processed = process_next_import_job() or process_next_recipe_url_import()
print("processed" if processed else "idle")
PY
