#!/usr/bin/env bash
set -euo pipefail

COMPOSE_CMD="${COMPOSE_CMD:-docker compose}"

${COMPOSE_CMD} exec -T api python -m app.cli seed-e2e --json | tail -n 1
