#!/usr/bin/env bash

set -euo pipefail

WEB_URL="${WEB_URL:-http://localhost:3000}"
API_URL="${API_URL:-http://localhost:8000}"
COMPOSE_CMD="${COMPOSE_CMD:-docker compose}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-120}"
POLL_SECONDS="${POLL_SECONDS:-2}"

read -r -a COMPOSE_ARGS <<<"${COMPOSE_CMD}"

usage() {
  cat <<'EOF'
Usage: smoke-check.sh

Environment:
  WEB_URL          Public web URL to probe. Default: http://localhost:3000
  API_URL          Public API URL to probe. Default: http://localhost:8000
  COMPOSE_CMD      Compose command for container checks. Default: docker compose
  TIMEOUT_SECONDS  Per-check timeout in seconds. Default: 120
  POLL_SECONDS     Poll interval in seconds. Default: 2

Checks:
  - web routes and same-origin API proxy
  - API readiness, including database, Alembic head, and Redis checks
  - direct Postgres and Redis container readiness
  - worker status command
EOF
}

die() {
  echo "Error: $*" >&2
  exit 1
}

log_step() {
  echo "==> $*"
}

require_command() {
  local command_name="$1"
  command -v "${command_name}" >/dev/null 2>&1 || die "Missing required command: ${command_name}"
}

compose() {
  "${COMPOSE_ARGS[@]}" "$@"
}

check_http() {
  local name="$1"
  local url="$2"
  local expected="$3"

  echo "Checking ${name}: ${url}"
  local body
  body="$(curl --fail --silent --show-error --location --connect-timeout 5 --max-time 10 "$url")"

  if [[ "$body" != *"$expected"* ]]; then
    die "Expected '${expected}' in response from ${url}"
  fi
}

wait_for_http() {
  local name="$1"
  local url="$2"
  local expected="$3"
  local deadline=$((SECONDS + TIMEOUT_SECONDS))
  local last_error=""
  local output

  while [[ "${SECONDS}" -lt "${deadline}" ]]; do
    if output="$(check_http "${name}" "${url}" "${expected}" 2>&1)"; then
      return 0
    fi
    last_error="${output}"
    sleep "${POLL_SECONDS}"
  done

  printf '%s\n' "${last_error}" >&2
  die "Timed out waiting for ${name} at ${url}"
}

check_api_ready_json() {
  local ready_json="$1"
  python3 - "${ready_json}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
expected = {
    "status": "ok",
    "database.status": "ok",
    "migrations.status": "ok",
    "redis.status": "ok",
}

def nested_get(data, path):
    current = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current

for path, expected_value in expected.items():
    actual_value = nested_get(payload, path)
    if actual_value != expected_value:
        raise SystemExit(
            f"API readiness {path}={actual_value!r}; expected {expected_value!r}."
        )

current_revision = nested_get(payload, "migrations.current_revision")
expected_revision = nested_get(payload, "migrations.expected_revision")
if not current_revision or current_revision != expected_revision:
    raise SystemExit(
        "API readiness migration revision mismatch: "
        f"current={current_revision!r} expected={expected_revision!r}."
    )
PY
}

wait_for_ready_json() {
  local name="$1"
  local ready_url="$2"
  local deadline=$((SECONDS + TIMEOUT_SECONDS))
  local ready_json=""
  local status

  while [[ "${SECONDS}" -lt "${deadline}" ]]; do
    ready_json="$(curl --silent --show-error --location --connect-timeout 5 --max-time 10 \
      --write-out '\n%{http_code}' "${ready_url}" || true)"
    status="${ready_json##*$'\n'}"
    ready_json="${ready_json%$'\n'*}"

    if [[ "${status}" =~ ^2[0-9][0-9]$ ]] && check_api_ready_json "${ready_json}" 2>/dev/null; then
      return 0
    fi

    sleep "${POLL_SECONDS}"
  done

  if ! check_api_ready_json "${ready_json}" 2>/dev/null; then
    printf 'Last %s readiness response from %s:\n%s\n' "${name}" "${ready_url}" "${ready_json}" >&2
  fi
  die "Timed out waiting for ${name} readiness at ${ready_url}"
}

check_worker_status() {
  local worker_status="$1"
  python3 - "${worker_status}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
if payload.get("status") != "ok":
    raise SystemExit(f"Worker status was {payload.get('status')!r}; expected 'ok'.")
PY
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

require_command curl
require_command python3
require_command "${COMPOSE_ARGS[0]}"

log_step "Checking Compose access"
compose ps >/dev/null || die "Unable to inspect the Docker Compose stack. Start it first with ./pantro start --demo or set COMPOSE_CMD."

log_step "Checking web container API wiring"
web_internal_api_url="$(compose exec -T web sh -lc 'printf %s "${INTERNAL_API_BASE_URL:-}"')"

if [[ -z "$web_internal_api_url" ]]; then
  die "INTERNAL_API_BASE_URL is not set in the running web container. Recreate the web container so Compose can inject the internal API URL."
fi

log_step "Checking web and API HTTP readiness"
wait_for_http "web home" "${WEB_URL}/" "Welcome back"
check_http "web login" "${WEB_URL}/login" "Username or email"
check_http "api health" "${API_URL}/api/health" "\"status\":\"ok\""
wait_for_ready_json "web API proxy" "${WEB_URL}/api/ready"
wait_for_ready_json "API" "${API_URL}/api/ready"

log_step "Checking database and Redis containers"
compose exec -T postgres sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null
redis_status="$(compose exec -T redis redis-cli ping)"
[[ "${redis_status}" == "PONG" ]] || die "Redis ping returned ${redis_status}; expected PONG."

log_step "Checking worker status"
worker_status="$(compose exec -T worker python -m worker.main --status)"
check_worker_status "${worker_status}"

echo "Smoke checks passed"
