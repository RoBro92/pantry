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
REPOSITORY="${PANTRY_REPOSITORY:-${PANTRY_DEFAULT_REPOSITORY}}"
VERSION_INPUT="${PANTRY_VERSION:-latest}"
REFRESH_ASSETS=1
ASSUME_YES=0

usage() {
  cat <<'EOF'
Usage: update-pantry.sh [--install-dir DIR] [--version X.Y.Z] [--repository OWNER/REPO] [--skip-assets] [--yes]
EOF
}

resolve_target_version() {
  local resolved_version

  if [[ -n "${VERSION_INPUT}" && "${VERSION_INPUT}" != "latest" ]]; then
    printf '%s' "${VERSION_INPUT}"
    return 0
  fi

  resolved_version="$(fetch_latest_release_version "${REPOSITORY}" 2>/dev/null || true)"
  [[ -n "${resolved_version}" ]] || die "Unable to resolve the latest Pantro release from GitHub."
  printf '%s' "${resolved_version}"
}

refresh_public_assets() {
  local target_version="$1"
  local asset_ref="v${target_version}"

  if [[ "${REFRESH_ASSETS}" -ne 1 ]]; then
    log_info "Keeping the existing pantry.yml and pantry.env.example."
    return 0
  fi

  log_step "Refreshing pantry.yml and pantry.env.example from ${asset_ref}"
  backup_file "${INSTALL_DIR}/pantry.yml"
  backup_file "${INSTALL_DIR}/pantry.env.example"

  copy_or_download_asset \
    "${PANTRY_REPO_ROOT}/infra/compose/pantry.yml" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/compose/pantry.yml" \
    "${INSTALL_DIR}/pantry.yml" \
    "${target_version}"
  copy_or_download_asset \
    "${PANTRY_REPO_ROOT}/infra/env/pantry.env.example" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/env/pantry.env.example" \
    "${INSTALL_DIR}/pantry.env.example" \
    "${target_version}"
}

main() {
  local env_file current_version target_version
  local web_url api_url

  require_command curl
  require_command docker
  require_command mktemp
  require_command python3

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --install-dir)
        INSTALL_DIR="$2"
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
      --skip-assets)
        REFRESH_ASSETS=0
        shift
        ;;
      --yes)
        ASSUME_YES=1
        shift
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

  current_version="$(env_get "${env_file}" "PANTRY_VERSION" "unknown")"
  target_version="$(resolve_target_version)"
  web_url="$(env_get "${env_file}" "WEB_APP_URL" "unknown")"
  api_url="$(env_get "${env_file}" "API_BASE_URL" "unknown")"

  log_step "Preparing Pantro update"
  log_info "Current version: ${current_version}"
  log_info "Target version: ${target_version}"

  if [[ "${current_version}" == "${target_version}" ]]; then
    log_info "Pantro is already pinned to ${target_version}."
    exit 0
  fi

  if [[ "${ASSUME_YES}" -ne 1 ]]; then
    prompt_yes_no "Continue with the update?" "n" || exit 1
  fi

  refresh_public_assets "${target_version}"

  log_step "Updating .env"
  env_set "${env_file}" "PANTRY_VERSION" "${target_version}"
  env_set "${env_file}" "PANTRY_IMAGE_NAMESPACE" "$(env_get "${env_file}" "PANTRY_IMAGE_NAMESPACE" "${PANTRY_DEFAULT_IMAGE_NAMESPACE}")"
  env_set "${env_file}" "RELEASE_CHECK_REPOSITORY" "$(env_get "${env_file}" "RELEASE_CHECK_REPOSITORY" "${REPOSITORY}")"

  log_step "Pulling Pantro images"
  docker_compose_in_dir "${INSTALL_DIR}" pull

  log_step "Refreshing core services"
  docker_compose_in_dir "${INSTALL_DIR}" up -d postgres redis

  log_step "Running database migrations"
  docker_compose_in_dir "${INSTALL_DIR}" --profile manual run --rm migrate

  log_step "Restarting the Pantro stack"
  docker_compose_in_dir "${INSTALL_DIR}" up -d --remove-orphans

  log_step "Running post-update health check"
  "${INSTALL_DIR}/healthcheck-pantry.sh" --install-dir "${INSTALL_DIR}" --timeout 180

  cat <<EOF

${PANTRY_COLOR_GREEN}Pantro update complete.${PANTRY_COLOR_RESET}
Current version: ${target_version}
Web URL: ${web_url}
API URL: ${api_url}

Useful commands:
  docker compose --env-file ${env_file} -f ${INSTALL_DIR}/pantry.yml ps
  docker compose --env-file ${env_file} -f ${INSTALL_DIR}/pantry.yml logs -f api
  docker compose --env-file ${env_file} -f ${INSTALL_DIR}/pantry.yml logs -f worker
EOF
}

main "$@"
