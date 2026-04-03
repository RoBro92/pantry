#!/usr/bin/env bash
set -euo pipefail

COMPOSE_CMD="${COMPOSE_CMD:-docker compose}"

${COMPOSE_CMD} exec -T api python - <<'PY'
from app.core.db import SessionLocal
from app.services.e2e_seed import reset_application_data

with SessionLocal() as db:
    reset_application_data(db)
PY
