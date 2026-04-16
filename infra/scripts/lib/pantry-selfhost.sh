#!/usr/bin/env bash

PANTRY_SELFHOST_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PANTRY_REPO_ROOT="$(cd "${PANTRY_SELFHOST_LIB_DIR}/../../.." && pwd)"
PANTRY_DEFAULT_REPOSITORY="${PANTRY_REPOSITORY:-RoBro92/pantry}"
PANTRY_DEFAULT_IMAGE_NAMESPACE="${PANTRY_IMAGE_NAMESPACE:-ghcr.io/robro92}"

if [[ -t 1 ]]; then
  PANTRY_COLOR_BLUE=$'\033[1;34m'
  PANTRY_COLOR_GREEN=$'\033[1;32m'
  PANTRY_COLOR_YELLOW=$'\033[1;33m'
  PANTRY_COLOR_RED=$'\033[1;31m'
  PANTRY_COLOR_RESET=$'\033[0m'
else
  PANTRY_COLOR_BLUE=""
  PANTRY_COLOR_GREEN=""
  PANTRY_COLOR_YELLOW=""
  PANTRY_COLOR_RED=""
  PANTRY_COLOR_RESET=""
fi

log_step() {
  printf '%s==>%s %s\n' "${PANTRY_COLOR_BLUE}" "${PANTRY_COLOR_RESET}" "$*"
}

log_info() {
  printf '%s[info]%s %s\n' "${PANTRY_COLOR_GREEN}" "${PANTRY_COLOR_RESET}" "$*"
}

log_warn() {
  printf '%s[warn]%s %s\n' "${PANTRY_COLOR_YELLOW}" "${PANTRY_COLOR_RESET}" "$*" >&2
}

log_error() {
  printf '%s[error]%s %s\n' "${PANTRY_COLOR_RED}" "${PANTRY_COLOR_RESET}" "$*" >&2
}

die() {
  log_error "$*"
  exit 1
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

require_command() {
  command_exists "$1" || die "Required command not found: $1"
}

require_root() {
  [[ "${EUID}" -eq 0 ]] || die "Run this script as root."
}

read_local_version() {
  if [[ -f "${PANTRY_REPO_ROOT}/VERSION" ]]; then
    tr -d '[:space:]' < "${PANTRY_REPO_ROOT}/VERSION"
  fi
}

env_get() {
  local env_file="$1"
  local key="$2"
  local default_value="${3:-}"
  local line

  line="$(grep -E "^${key}=" "${env_file}" | tail -n 1 || true)"
  if [[ -z "${line}" ]]; then
    printf '%s' "${default_value}"
    return 0
  fi

  printf '%s' "${line#*=}"
}

env_set() {
  local env_file="$1"
  local key="$2"
  local value="$3"
  local tmp_file

  tmp_file="$(mktemp)"
  awk -v key="${key}" -v value="${value}" '
    BEGIN { replaced = 0 }
    $0 ~ ("^" key "=") {
      print key "=" value
      replaced = 1
      next
    }
    { print }
    END {
      if (!replaced) {
        print key "=" value
      }
    }
  ' "${env_file}" > "${tmp_file}"
  mv "${tmp_file}" "${env_file}"
}

prompt_with_default() {
  local prompt="$1"
  local default_value="${2:-}"
  local reply

  if [[ ! -t 0 ]]; then
    printf '%s' "${default_value}"
    return 0
  fi

  if [[ -n "${default_value}" ]]; then
    read -r -p "${prompt} [${default_value}]: " reply
    printf '%s' "${reply:-${default_value}}"
    return 0
  fi

  read -r -p "${prompt}: " reply
  printf '%s' "${reply}"
}

prompt_yes_no() {
  local prompt="$1"
  local default_answer="${2:-n}"
  local reply

  if [[ ! -t 0 ]]; then
    [[ "${default_answer}" =~ ^[Yy]$ ]]
    return 0
  fi

  if [[ "${default_answer}" =~ ^[Yy]$ ]]; then
    read -r -p "${prompt} [Y/n]: " reply
    reply="${reply:-Y}"
  else
    read -r -p "${prompt} [y/N]: " reply
    reply="${reply:-N}"
  fi

  [[ "${reply}" =~ ^[Yy]$ ]]
}

generate_secret() {
  if command_exists openssl; then
    openssl rand -hex 32
    return 0
  fi

  if command_exists python3; then
    python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
    return 0
  fi

  if [[ -r /dev/urandom ]]; then
    LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 64
    printf '\n'
    return 0
  fi

  die "Unable to generate a random secret."
}

canonical_arch() {
  case "$(uname -m)" in
    x86_64|amd64)
      printf 'amd64'
      ;;
    aarch64|arm64)
      printf 'arm64'
      ;;
    *)
      return 1
      ;;
  esac
}

detect_primary_ip() {
  local detected_ip

  detected_ip="$(ip route get 1.1.1.1 2>/dev/null | awk '/src/ {print $7; exit}' || true)"
  if [[ -n "${detected_ip}" ]]; then
    printf '%s' "${detected_ip}"
    return 0
  fi

  detected_ip="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
  printf '%s' "${detected_ip:-127.0.0.1}"
}

raw_github_url() {
  local repository="$1"
  local ref="$2"
  local path="$3"

  printf 'https://raw.githubusercontent.com/%s/%s/%s' "${repository}" "${ref}" "${path}"
}

copy_or_download_asset() {
  local local_source="$1"
  local repository="$2"
  local ref="$3"
  local repo_path="$4"
  local destination="$5"
  local expected_version="$6"
  local local_version

  local_version="$(read_local_version || true)"
  if [[ -f "${local_source}" && -n "${local_version}" && "${local_version}" == "${expected_version}" ]]; then
    cp "${local_source}" "${destination}"
    return 0
  fi

  require_command curl
  curl -fsSL "$(raw_github_url "${repository}" "${ref}" "${repo_path}")" -o "${destination}"
}

fetch_latest_release_version() {
  local repository="$1"

  require_command python3
  python3 - "${repository}" <<'PY'
import json
import sys
import urllib.request

repository = sys.argv[1]
url = f"https://api.github.com/repos/{repository}/releases/latest"

request = urllib.request.Request(
    url,
    headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "Pantro installer",
    },
)

with urllib.request.urlopen(request, timeout=10) as response:
    payload = json.load(response)

tag = str(payload.get("tag_name") or "").strip()
if not tag:
    raise SystemExit("Latest release metadata did not include tag_name.")

print(tag[1:] if tag.lower().startswith("v") else tag)
PY
}

check_http_endpoint() {
  local url="$1"
  local status

  require_command curl
  status="$(curl -sSIL -o /dev/null -w '%{http_code}' "${url}" || true)"
  [[ "${status}" != "000" ]]
}

wait_for_http_ok() {
  local url="$1"
  local timeout_seconds="$2"
  local deadline=$((SECONDS + timeout_seconds))

  require_command curl
  while (( SECONDS < deadline )); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  return 1
}

backup_file() {
  local path="$1"

  if [[ -f "${path}" ]]; then
    cp "${path}" "${path}.bak.$(date +%Y%m%d%H%M%S)"
  fi
}

docker_compose_in_dir() {
  local install_dir="$1"
  shift

  docker compose --env-file "${install_dir}/.env" -f "${install_dir}/pantry.yml" "$@"
}
