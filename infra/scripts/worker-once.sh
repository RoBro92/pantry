#!/usr/bin/env bash
set -euo pipefail

COMPOSE_CMD="${COMPOSE_CMD:-docker compose}"

${COMPOSE_CMD} exec -T api python - <<'PY'
from app.services.import_processing import process_next_import_job
from app.services.recipe_url_imports import process_next_recipe_url_import

processed = process_next_import_job() or process_next_recipe_url_import()
print("processed" if processed else "idle")
PY
