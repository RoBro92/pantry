#!/usr/bin/env bash

set -euo pipefail

WEB_URL="${WEB_URL:-http://localhost:3000}"
API_URL="${API_URL:-http://localhost:8000}"
COMPOSE_CMD="${COMPOSE_CMD:-docker compose}"

check_http() {
  local name="$1"
  local url="$2"
  local expected="$3"

  echo "Checking ${name}: ${url}"
  local body
  body="$(curl --fail --silent --show-error --location "$url")"

  if [[ "$body" != *"$expected"* ]]; then
    echo "Expected '${expected}' in response from ${url}" >&2
    exit 1
  fi
}

echo "Checking web container API wiring"
web_internal_api_url="$(${COMPOSE_CMD} exec -T web sh -lc 'printf %s "${INTERNAL_API_BASE_URL:-}"')"

if [[ -z "$web_internal_api_url" ]]; then
  echo "INTERNAL_API_BASE_URL is not set in the running web container." >&2
  echo "Recreate the web container with docker compose up -d --build so Compose can inject the expected internal API URL." >&2
  exit 1
fi

check_http "web home" "${WEB_URL}/" "Welcome back"
check_http "web login" "${WEB_URL}/login" "Username or email"
check_http "api health" "${API_URL}/api/health" "\"status\":\"ok\""

echo "Checking worker status"
worker_status="$(${COMPOSE_CMD} exec -T worker python -m worker.main --status)"

if [[ "$worker_status" != *"\"status\": \"ok\""* && "$worker_status" != *"\"status\":\"ok\""* ]]; then
  echo "Unexpected worker status output: ${worker_status}" >&2
  exit 1
fi

echo "Smoke checks passed"
