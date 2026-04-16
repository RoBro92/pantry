#!/usr/bin/env bash
set -euo pipefail

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
DOCKER_COMPOSE_BIN="${DOCKER_COMPOSE_BIN:-docker compose}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEFAULT_DEV_ENV_FILE="${ROOT_DIR}/.env.local"
LEGACY_DEV_ENV_FILE="${ROOT_DIR}/.env"
LOCAL_DEV_ENV_TEMPLATE_FILE="${ROOT_DIR}/.env.local.example"
EXAMPLE_ENV_FILE="${ROOT_DIR}/.env.example"

read -r -a COMPOSE_CMD <<<"${DOCKER_COMPOSE_BIN}"

detect_polling_default() {
  case "$(uname -s)" in
    Darwin|MINGW*|MSYS*|CYGWIN*)
      printf 'true\n'
      ;;
    *)
      printf 'false\n'
      ;;
  esac
}

compose() {
  "${COMPOSE_CMD[@]}" --env-file "${DEV_ENV_FILE}" -f "${ROOT_DIR}/compose.yml" -f "${ROOT_DIR}/compose.dev.yml" "$@"
}

bootstrap_dev_env() {
  if [[ -n "${PANTRY_DEV_ENV_FILE:-}" ]]; then
    DEV_ENV_FILE="${PANTRY_DEV_ENV_FILE}"
  elif [[ -f "${DEFAULT_DEV_ENV_FILE}" ]]; then
    DEV_ENV_FILE="${DEFAULT_DEV_ENV_FILE}"
  elif [[ -f "${LEGACY_DEV_ENV_FILE}" ]]; then
    DEV_ENV_FILE="${LEGACY_DEV_ENV_FILE}"
  else
    local template_source
    if [[ -f "${LOCAL_DEV_ENV_TEMPLATE_FILE}" ]]; then
      cp "${LOCAL_DEV_ENV_TEMPLATE_FILE}" "${DEFAULT_DEV_ENV_FILE}"
      template_source="${LOCAL_DEV_ENV_TEMPLATE_FILE}"
    else
      cp "${EXAMPLE_ENV_FILE}" "${DEFAULT_DEV_ENV_FILE}"
      template_source="${EXAMPLE_ENV_FILE}"
    fi
    DEV_ENV_FILE="${DEFAULT_DEV_ENV_FILE}"
    echo "Created ${DEV_ENV_FILE} from $(basename "${template_source}") for local development."
  fi

  export PANTRY_WEB_WATCHPACK_POLLING="${PANTRY_WEB_WATCHPACK_POLLING:-$(detect_polling_default)}"
  export PANTRY_WEB_CHOKIDAR_USEPOLLING="${PANTRY_WEB_CHOKIDAR_USEPOLLING:-${PANTRY_WEB_WATCHPACK_POLLING}}"
  export PANTRY_WEB_CHOKIDAR_INTERVAL="${PANTRY_WEB_CHOKIDAR_INTERVAL:-500}"
  export PANTRY_API_WATCHFILES_FORCE_POLLING="${PANTRY_API_WATCHFILES_FORCE_POLLING:-${PANTRY_WEB_WATCHPACK_POLLING}}"
  export PANTRY_WORKER_WATCHFILES_FORCE_POLLING="${PANTRY_WORKER_WATCHFILES_FORCE_POLLING:-${PANTRY_WEB_WATCHPACK_POLLING}}"
}

usage() {
  cat <<'EOF'
Development-only local stack helper.

Usage:
  ./infra/scripts/dev-stack.sh start <fresh|demo>
  ./infra/scripts/dev-stack.sh reset <fresh|demo>
  ./infra/scripts/dev-stack.sh rebuild
  ./infra/scripts/dev-stack.sh down
  ./infra/scripts/dev-stack.sh logs
  ./infra/scripts/dev-stack.sh status

Modes:
  fresh  Reset to an uninitialized first-run state and land on /setup
  demo   Reset and seed stable demo data, then land on /login

Notes:
  - Uses .env.local by default, falls back to .env if present, and bootstraps .env.local from .env.local.example when needed.
  - Start replaces the whole local dev stack so web, api, and worker all come up fresh together.
  - Reset re-seeds the running stack without forcing container replacement.
  - Use rebuild after Dockerfile or dependency changes.
  - Docker Desktop file polling is enabled automatically on macOS and Windows-like shells.

This helper does not change the production or self-hosted install flow in infra/compose/pantry.yml.
EOF
}

wait_for_api() {
  local health_url="http://localhost:${API_PORT}/api/health"
  local attempt

  for attempt in $(seq 1 60); do
    if curl -fsS "${health_url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  echo "Timed out waiting for API health at ${health_url}." >&2
  return 1
}

bootstrap_mode() {
  local mode="$1"
  compose exec -T api python -m app.cli seed-development-mode --mode "${mode}" --json | tail -n 1
}

start_stack() {
  compose down --remove-orphans --volumes
  compose up -d --remove-orphans --force-recreate
  wait_for_api
}

ensure_stack_running() {
  compose up -d --remove-orphans
  wait_for_api
}

run_mode() {
  local action="$1"
  local mode="${2:-}"

  if [[ -z "${mode}" ]]; then
    usage >&2
    exit 1
  fi

  case "${mode}" in
    fresh|demo)
      ;;
    *)
      echo "Unknown mode: ${mode}" >&2
      usage >&2
      exit 1
      ;;
  esac

  if [[ "${action}" == "start" ]]; then
    start_stack
  else
    ensure_stack_running
  fi

  local manifest
  manifest="$(bootstrap_mode "${mode}")"
  printf '%s\n' "${manifest}"
  echo
  echo "Pantry local development mode: ${mode}"
  echo "Open: http://localhost:${WEB_PORT}/"
}

main() {
  local command="${1:-}"
  bootstrap_dev_env

  case "${command}" in
    start)
      run_mode "start" "${2:-}"
      ;;
    reset)
      run_mode "reset" "${2:-}"
      ;;
    down)
      compose down --remove-orphans
      ;;
    logs)
      compose logs -f web api worker
      ;;
    status)
      compose ps
      ;;
    rebuild)
      compose down --remove-orphans
      compose up -d --build --remove-orphans --force-recreate
      wait_for_api
      ;;
    help)
      usage
      ;;
    *)
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"
