#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PANTRY_SELFHOST_LIB="${SCRIPT_DIR}/lib/pantry-selfhost.sh"
if [[ ! -f "${PANTRY_SELFHOST_LIB}" ]]; then
  REPOSITORY_FALLBACK="${PANTRY_REPOSITORY:-RoBro92/pantry}"
  mkdir -p "${SCRIPT_DIR}/lib"
  curl -fsSL "https://raw.githubusercontent.com/${REPOSITORY_FALLBACK}/main/infra/scripts/lib/pantry-selfhost.sh" -o "${PANTRY_SELFHOST_LIB}"
fi
# shellcheck source=infra/scripts/lib/pantry-selfhost.sh
source "${PANTRY_SELFHOST_LIB}"

INSTALL_DIR="${PANTRY_INSTALL_DIR:-/opt/pantry}"
TIMEOUT_SECONDS=120

usage() {
  cat <<'EOF'
Usage: healthcheck-pantry.sh [--install-dir DIR] [--timeout SECONDS]
EOF
}

main() {
  local env_file web_url api_url
  local web_status_json api_health_json setup_status_json worker_status_json
  local compose_ps

  require_command curl
  require_command docker
  require_command python3

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --install-dir)
        INSTALL_DIR="$2"
        shift 2
        ;;
      --timeout)
        TIMEOUT_SECONDS="$2"
        shift 2
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        die "Unknown argument: $1"
        ;;
    esac
  done

  env_file="${INSTALL_DIR}/.env"
  [[ -f "${INSTALL_DIR}/pantry.yml" ]] || die "Missing ${INSTALL_DIR}/pantry.yml"
  [[ -f "${env_file}" ]] || die "Missing ${env_file}"

  web_url="$(env_get "${env_file}" "WEB_APP_URL" "")"
  api_url="$(env_get "${env_file}" "API_BASE_URL" "")"
  [[ -n "${web_url}" ]] || die "WEB_APP_URL is not set in ${env_file}"
  [[ -n "${api_url}" ]] || die "API_BASE_URL is not set in ${env_file}"

  log_step "Waiting for Pantry services"
  wait_for_http_ok "${web_url}/" "${TIMEOUT_SECONDS}" || die "Web health check timed out at ${web_url}/"
  wait_for_http_ok "${api_url}/api/health" "${TIMEOUT_SECONDS}" || die "API health check timed out at ${api_url}/api/health"

  log_step "Inspecting running containers"
  compose_ps="$(docker_compose_in_dir "${INSTALL_DIR}" ps)"
  printf '%s\n' "${compose_ps}"

  log_step "Checking web, API, setup, and worker status"
  web_status_json="$(curl -fsS "${web_url}/" >/dev/null && printf '{"status":"ok"}')"
  api_health_json="$(curl -fsS "${api_url}/api/health")"
  setup_status_json="$(curl -fsS "${api_url}/api/setup/status")"
  worker_status_json="$(docker_compose_in_dir "${INSTALL_DIR}" exec -T worker python -m worker.main --status)"

  python3 - "${api_health_json}" "${setup_status_json}" "${worker_status_json}" "${web_url}" "${api_url}" <<'PY'
import json
import sys

api_health = json.loads(sys.argv[1])
setup_status = json.loads(sys.argv[2])
worker_output = json.loads(sys.argv[3])
web_url = sys.argv[4]
api_url = sys.argv[5]

if api_health.get("status") != "ok":
    raise SystemExit("API did not report status=ok.")
if worker_output.get("status") != "ok":
    raise SystemExit("Worker did not report status=ok.")

print()
print("Pantry health summary")
print(f"  Web: ok ({web_url})")
print(f"  API: {api_health.get('status')} ({api_url}/api/health)")
print(f"  Version: {api_health.get('version')}")
print(f"  Setup initialized: {setup_status.get('is_initialized')}")
print(f"  Platform admins: {setup_status.get('platform_admin_count')}")
print(f"  Worker: {worker_output.get('status')}")
print(f"  Next step: {setup_status.get('recommended_next_step')}")
PY
}

main "$@"
