#!/usr/bin/env bash
set -euo pipefail

COMPOSE_CMD="${COMPOSE_CMD:-docker compose}"

${COMPOSE_CMD} exec -T worker python -m worker.main --once
