#!/usr/bin/env bash
set -euo pipefail

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
DOCKER_COMPOSE_BIN="${DOCKER_COMPOSE_BIN:-docker compose}"

compose() {
  ${DOCKER_COMPOSE_BIN} -f compose.yml -f compose.dev.yml "$@"
}

usage() {
  cat <<'EOF'
Development-only local stack helper.

Usage:
  ./infra/scripts/dev-stack.sh start <fresh|demo>
  ./infra/scripts/dev-stack.sh reset <fresh|demo>
  ./infra/scripts/dev-stack.sh down
  ./infra/scripts/dev-stack.sh logs

Modes:
  fresh  Reset to an uninitialized first-run state and land on /setup
  demo   Reset and seed stable demo data, then land on /login

This does not change the production or self-hosted install flow.
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
  compose up -d --build
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
    compose up -d
    wait_for_api
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

  case "${command}" in
    start)
      run_mode "start" "${2:-}"
      ;;
    reset)
      run_mode "reset" "${2:-}"
      ;;
    down)
      compose down
      ;;
    logs)
      compose logs -f web api worker
      ;;
    *)
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"
