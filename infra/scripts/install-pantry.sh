#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  SCRIPT_DIR="$(mktemp -d)"
  trap 'rm -rf "${SCRIPT_DIR}"' EXIT
fi

PANTRY_SELFHOST_LIB="${SCRIPT_DIR}/lib/pantry-selfhost.sh"
if [[ ! -f "${PANTRY_SELFHOST_LIB}" ]]; then
  REPOSITORY_FALLBACK="${PANTRY_REPOSITORY:-RoBro92/pantry}"
  mkdir -p "${SCRIPT_DIR}/lib"
  curl -fsSL "https://raw.githubusercontent.com/${REPOSITORY_FALLBACK}/main/infra/scripts/lib/pantry-selfhost.sh" -o "${PANTRY_SELFHOST_LIB}"
fi
# shellcheck source=infra/scripts/lib/pantry-selfhost.sh
source "${PANTRY_SELFHOST_LIB}"

INSTALL_DIR="${PANTRY_INSTALL_DIR:-/opt/pantry}"
DATA_ROOT="${PANTRY_DATA_ROOT:-/srv/pantry}"
REPOSITORY="${PANTRY_REPOSITORY:-${PANTRY_DEFAULT_REPOSITORY}}"
VERSION_INPUT="${PANTRY_VERSION:-latest}"

check_os_and_arch() {
  local arch
  local virtualization

  [[ -f /etc/os-release ]] || die "Cannot determine the operating system."
  # shellcheck disable=SC1091
  source /etc/os-release

  [[ "${ID:-}" == "debian" ]] || die "This installer targets Debian LXC hosts."
  arch="$(canonical_arch)" || die "Unsupported architecture: $(uname -m). Supported: amd64, arm64."
  log_info "Detected Debian ${VERSION_ID:-unknown} on ${arch}."

  if command_exists systemd-detect-virt; then
    virtualization="$(systemd-detect-virt 2>/dev/null || true)"
    if [[ "${virtualization}" != "lxc" ]]; then
      log_warn "Detected virtualization '${virtualization:-none}'. Continuing because Docker may still work."
    fi
  fi
}

check_network() {
  log_step "Checking network access"
  check_http_endpoint "https://api.github.com" || die "Cannot reach api.github.com."
  check_http_endpoint "https://ghcr.io/v2/" || die "Cannot reach ghcr.io."
  log_info "GitHub API and GHCR are reachable."
}

install_docker_if_needed() {
  local need_install=0

  if ! command_exists docker; then
    need_install=1
  elif ! docker compose version >/dev/null 2>&1; then
    need_install=1
  fi

  if [[ "${need_install}" -eq 0 ]]; then
    log_info "Docker Engine and the Compose plugin are already available."
    return 0
  fi

  log_step "Installing Docker Engine and Docker Compose plugin"
  # shellcheck disable=SC1091
  source /etc/os-release

  apt-get update
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  cat > /etc/apt/sources.list.d/docker.list <<EOF
deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable
EOF
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  if command_exists systemctl; then
    systemctl enable --now docker
  fi

  docker info >/dev/null
  log_info "Docker is ready."
}

resolve_install_version() {
  local resolved_version

  if [[ -n "${VERSION_INPUT}" && "${VERSION_INPUT}" != "latest" ]]; then
    printf '%s' "${VERSION_INPUT}"
    return 0
  fi

  resolved_version="$(fetch_latest_release_version "${REPOSITORY}" 2>/dev/null || true)"
  if [[ -n "${resolved_version}" ]]; then
    printf '%s' "${resolved_version}"
    return 0
  fi

  resolved_version="$(read_local_version || true)"
  [[ -n "${resolved_version}" ]] || die "Unable to resolve a Pantry version to install."
  log_warn "Falling back to the local repository VERSION because the latest GitHub release could not be read."
  printf '%s' "${resolved_version}"
}

prepare_install_layout() {
  local selected_version="$1"
  local asset_ref="v${selected_version}"

  log_step "Preparing ${INSTALL_DIR}"
  mkdir -p "${INSTALL_DIR}"
  mkdir -p "${DATA_ROOT}/postgres" "${DATA_ROOT}/redis" "${DATA_ROOT}/imports"

  if [[ -f "${INSTALL_DIR}/.env" ]]; then
    die "${INSTALL_DIR}/.env already exists. Use update-pantry.sh for existing installs."
  fi

  copy_or_download_asset \
    "${PANTRY_REPO_ROOT}/infra/compose/pantry.yml" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/compose/pantry.yml" \
    "${INSTALL_DIR}/pantry.yml" \
    "${selected_version}"
  copy_or_download_asset \
    "${PANTRY_REPO_ROOT}/infra/env/pantry.env.example" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/env/pantry.env.example" \
    "${INSTALL_DIR}/pantry.env.example" \
    "${selected_version}"

  cp "${INSTALL_DIR}/pantry.env.example" "${INSTALL_DIR}/.env"
}

configure_env_file() {
  local selected_version="$1"
  local host="$2"
  local web_port="$3"
  local api_port="$4"
  local scheme="$5"
  local env_file="${INSTALL_DIR}/.env"
  local postgres_password settings_key session_key
  local browser_url api_url

  postgres_password="$(generate_secret)"
  settings_key="$(generate_secret)"
  session_key="$(generate_secret)"

  browser_url="${scheme}://${host}:${web_port}"
  api_url="${scheme}://${host}:${api_port}"

  log_step "Writing ${env_file}"
  env_set "${env_file}" "PANTRY_VERSION" "${selected_version}"
  env_set "${env_file}" "PANTRY_IMAGE_NAMESPACE" "${PANTRY_DEFAULT_IMAGE_NAMESPACE}"
  env_set "${env_file}" "WEB_BIND_ADDRESS" "0.0.0.0"
  env_set "${env_file}" "WEB_PORT" "${web_port}"
  env_set "${env_file}" "API_BIND_ADDRESS" "0.0.0.0"
  env_set "${env_file}" "API_PORT" "${api_port}"
  env_set "${env_file}" "POSTGRES_PASSWORD" "${postgres_password}"
  env_set "${env_file}" "DATABASE_URL" "postgresql+psycopg://pantry:${postgres_password}@postgres:5432/pantry"
  env_set "${env_file}" "WEB_APP_URL" "${browser_url}"
  env_set "${env_file}" "API_BASE_URL" "${api_url}"
  env_set "${env_file}" "PUBLIC_BROWSER_BASE_URL" "${browser_url}"
  env_set "${env_file}" "PANTRY_POSTGRES_DATA_DIR" "${DATA_ROOT}/postgres"
  env_set "${env_file}" "PANTRY_REDIS_DATA_DIR" "${DATA_ROOT}/redis"
  env_set "${env_file}" "PANTRY_IMPORTS_DATA_DIR" "${DATA_ROOT}/imports"
  env_set "${env_file}" "SETTINGS_ENCRYPTION_KEY" "${settings_key}"
  env_set "${env_file}" "SESSION_SECRET_KEY" "${session_key}"
  env_set "${env_file}" "SESSION_HTTPS_ONLY" "$([[ "${scheme}" == "https" ]] && printf 'true' || printf 'false')"
  env_set "${env_file}" "RELEASE_CHECK_REPOSITORY" "${REPOSITORY}"
}

run_install() {
  log_step "Pulling Pantry images"
  docker_compose_in_dir "${INSTALL_DIR}" pull

  log_step "Starting PostgreSQL and Redis"
  docker_compose_in_dir "${INSTALL_DIR}" up -d postgres redis

  log_step "Running database migrations"
  docker_compose_in_dir "${INSTALL_DIR}" --profile manual run --rm migrate

  log_step "Starting the Pantry stack"
  docker_compose_in_dir "${INSTALL_DIR}" up -d
}

print_summary() {
  local selected_version="$1"
  local browser_url="$2"
  local api_url="$3"

  cat <<EOF

${PANTRY_COLOR_GREEN}Pantry install complete.${PANTRY_COLOR_RESET}
Installed version: ${selected_version}
Install directory: ${INSTALL_DIR}
Web URL: ${browser_url}
API URL: ${api_url}

Useful commands:
  cd ${INSTALL_DIR}
  docker compose --env-file .env -f pantry.yml ps
  docker compose --env-file .env -f pantry.yml logs -f web
  docker compose --env-file .env -f pantry.yml logs -f api
  docker compose --env-file .env -f pantry.yml logs -f worker
  ./healthcheck-pantry.sh --install-dir ${INSTALL_DIR}
  ./update-pantry.sh --install-dir ${INSTALL_DIR}

First-run setup:
  Open ${browser_url}/ in a browser
  or run:
  docker compose --env-file .env -f pantry.yml run --rm api \\
    python -m app.cli bootstrap-platform-admin --email admin@example.com --display-name "Pantry Admin"

Password reset:
  docker compose --env-file .env -f pantry.yml run --rm api \\
    python -m app.cli reset-password --email admin@example.com
EOF
}

main() {
  local resolved_version detected_ip selected_version host web_port api_port use_https scheme asset_ref
  local browser_url api_url

  require_root
  require_command awk
  require_command cp
  require_command curl
  require_command grep
  require_command ip
  require_command mktemp
  require_command python3

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --install-dir)
        INSTALL_DIR="$2"
        shift 2
        ;;
      --data-root)
        DATA_ROOT="$2"
        shift 2
        ;;
      --version)
        VERSION_INPUT="$2"
        shift 2
        ;;
      --repository)
        REPOSITORY="$2"
        shift 2
        ;;
      *)
        die "Unknown argument: $1"
        ;;
    esac
  done

  log_step "Pantry self-hosted installer"
  check_os_and_arch
  check_network
  install_docker_if_needed

  resolved_version="$(resolve_install_version)"
  detected_ip="$(detect_primary_ip)"
  selected_version="$(prompt_with_default "Pantry version to install" "${resolved_version}")"
  host="$(prompt_with_default "Browser host or IP" "${detected_ip}")"
  web_port="$(prompt_with_default "Web port" "3000")"
  api_port="$(prompt_with_default "API port" "8000")"
  if prompt_yes_no "Use HTTPS for the browser and API URLs?" "n"; then
    use_https="yes"
  else
    use_https="no"
  fi
  scheme="$([[ "${use_https}" == "yes" ]] && printf 'https' || printf 'http')"
  asset_ref="v${selected_version}"

  prepare_install_layout "${selected_version}"
  configure_env_file "${selected_version}" "${host}" "${web_port}" "${api_port}" "${scheme}"
  mkdir -p "${INSTALL_DIR}/lib"
  copy_or_download_asset \
    "${PANTRY_REPO_ROOT}/infra/scripts/update-pantry.sh" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/scripts/update-pantry.sh" \
    "${INSTALL_DIR}/update-pantry.sh" \
    "${selected_version}"
  copy_or_download_asset \
    "${PANTRY_REPO_ROOT}/infra/scripts/healthcheck-pantry.sh" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/scripts/healthcheck-pantry.sh" \
    "${INSTALL_DIR}/healthcheck-pantry.sh" \
    "${selected_version}"
  copy_or_download_asset \
    "${PANTRY_REPO_ROOT}/infra/scripts/lib/pantry-selfhost.sh" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/scripts/lib/pantry-selfhost.sh" \
    "${INSTALL_DIR}/lib/pantry-selfhost.sh" \
    "${selected_version}"
  chmod +x "${INSTALL_DIR}/update-pantry.sh" "${INSTALL_DIR}/healthcheck-pantry.sh"

  run_install

  log_step "Running post-install health check"
  "${INSTALL_DIR}/healthcheck-pantry.sh" --install-dir "${INSTALL_DIR}" --timeout 180

  browser_url="${scheme}://${host}:${web_port}"
  api_url="${scheme}://${host}:${api_port}"
  print_summary "${selected_version}" "${browser_url}" "${api_url}"
}

main "$@"
