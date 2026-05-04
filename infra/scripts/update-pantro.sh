#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PANTRO_SELFHOST_LIB="${SCRIPT_DIR}/lib/pantro-selfhost.sh"
if [[ ! -f "${PANTRO_SELFHOST_LIB}" ]]; then
  REPOSITORY_FALLBACK="${PANTRO_REPOSITORY:-${PANTRY_REPOSITORY:-RoBro92/pantry}}"
  mkdir -p "${SCRIPT_DIR}/lib"
  curl -fsSL "https://raw.githubusercontent.com/${REPOSITORY_FALLBACK}/main/infra/scripts/lib/pantro-selfhost.sh" -o "${PANTRO_SELFHOST_LIB}"
fi
# shellcheck source=infra/scripts/lib/pantro-selfhost.sh
source "${PANTRO_SELFHOST_LIB}"

INSTALL_DIR="${PANTRO_INSTALL_DIR:-${PANTRY_INSTALL_DIR:-$(default_install_dir)}}"
REPOSITORY="${PANTRO_REPOSITORY:-${PANTRY_REPOSITORY:-${PANTRO_DEFAULT_REPOSITORY}}}"
VERSION_INPUT="${PANTRO_VERSION:-${PANTRY_VERSION:-latest}}"
REFRESH_ASSETS=1
ASSUME_YES=0

usage() {
  cat <<'EOF'
Usage: update-pantro.sh [--install-dir DIR] [--version X.Y.Z] [--repository OWNER/REPO] [--skip-assets] [--yes]
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

refresh_release_assets() {
  local target_version="$1"
  local asset_ref="v${target_version}"

  if [[ "${REFRESH_ASSETS}" -ne 1 ]]; then
    log_info "Keeping the existing self-hosted asset bundle."
    return 0
  fi

  log_step "Refreshing Pantro release assets from ${asset_ref}"
  mkdir -p "${INSTALL_DIR}/lib"
  backup_file "${INSTALL_DIR}/pantro.yml"
  backup_file "${INSTALL_DIR}/pantry.yml"
  backup_file "${INSTALL_DIR}/pantro.env.example"
  backup_file "${INSTALL_DIR}/pantry.env.example"
  backup_file "${INSTALL_DIR}/update-pantro.sh"
  backup_file "${INSTALL_DIR}/update-pantry.sh"
  backup_file "${INSTALL_DIR}/healthcheck-pantro.sh"
  backup_file "${INSTALL_DIR}/healthcheck-pantry.sh"
  backup_file "${INSTALL_DIR}/lib/pantro-selfhost.sh"
  backup_file "${INSTALL_DIR}/lib/pantry-selfhost.sh"

  copy_or_download_asset \
    "${PANTRO_REPO_ROOT}/infra/compose/pantro.yml" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/compose/pantro.yml" \
    "${INSTALL_DIR}/pantro.yml" \
    "${target_version}"
  copy_or_download_asset \
    "${PANTRO_REPO_ROOT}/infra/compose/pantry.yml" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/compose/pantry.yml" \
    "${INSTALL_DIR}/pantry.yml" \
    "${target_version}"
  copy_or_download_asset \
    "${PANTRO_REPO_ROOT}/infra/env/pantro.env.example" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/env/pantro.env.example" \
    "${INSTALL_DIR}/pantro.env.example" \
    "${target_version}"
  copy_or_download_asset \
    "${PANTRO_REPO_ROOT}/infra/env/pantry.env.example" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/env/pantry.env.example" \
    "${INSTALL_DIR}/pantry.env.example" \
    "${target_version}"
  copy_or_download_asset \
    "${PANTRO_REPO_ROOT}/infra/scripts/update-pantro.sh" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/scripts/update-pantro.sh" \
    "${INSTALL_DIR}/update-pantro.sh" \
    "${target_version}"
  copy_or_download_asset \
    "${PANTRO_REPO_ROOT}/infra/scripts/update-pantry.sh" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/scripts/update-pantry.sh" \
    "${INSTALL_DIR}/update-pantry.sh" \
    "${target_version}"
  copy_or_download_asset \
    "${PANTRO_REPO_ROOT}/infra/scripts/healthcheck-pantro.sh" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/scripts/healthcheck-pantro.sh" \
    "${INSTALL_DIR}/healthcheck-pantro.sh" \
    "${target_version}"
  copy_or_download_asset \
    "${PANTRO_REPO_ROOT}/infra/scripts/healthcheck-pantry.sh" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/scripts/healthcheck-pantry.sh" \
    "${INSTALL_DIR}/healthcheck-pantry.sh" \
    "${target_version}"
  copy_or_download_asset \
    "${PANTRO_REPO_ROOT}/infra/scripts/lib/pantro-selfhost.sh" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/scripts/lib/pantro-selfhost.sh" \
    "${INSTALL_DIR}/lib/pantro-selfhost.sh" \
    "${target_version}"
  copy_or_download_asset \
    "${PANTRO_REPO_ROOT}/infra/scripts/lib/pantry-selfhost.sh" \
    "${REPOSITORY}" \
    "${asset_ref}" \
    "infra/scripts/lib/pantry-selfhost.sh" \
    "${INSTALL_DIR}/lib/pantry-selfhost.sh" \
    "${target_version}"

  chmod +x \
    "${INSTALL_DIR}/update-pantro.sh" \
    "${INSTALL_DIR}/update-pantry.sh" \
    "${INSTALL_DIR}/healthcheck-pantro.sh" \
    "${INSTALL_DIR}/healthcheck-pantry.sh"
}

main() {
  local env_file compose_file current_version target_version image_namespace
  local postgres_data_dir redis_data_dir imports_data_dir backups_data_dir
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
  compose_file="$(resolve_install_compose_file "${INSTALL_DIR}")"
  [[ -f "${compose_file}" ]] || die "Missing a self-hosted compose file in ${INSTALL_DIR}"
  [[ -f "${env_file}" ]] || die "Missing ${env_file}"

  current_version="$(env_get_any "${env_file}" "unknown" "PANTRO_VERSION" "PANTRY_VERSION")"
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

  refresh_release_assets "${target_version}"

  image_namespace="$(env_get_any "${env_file}" "${PANTRO_DEFAULT_IMAGE_NAMESPACE}" "PANTRO_IMAGE_NAMESPACE" "PANTRY_IMAGE_NAMESPACE")"
  postgres_data_dir="$(env_get_any "${env_file}" "$(default_data_root)/postgres" "PANTRO_POSTGRES_DATA_DIR" "PANTRY_POSTGRES_DATA_DIR")"
  redis_data_dir="$(env_get_any "${env_file}" "$(default_data_root)/redis" "PANTRO_REDIS_DATA_DIR" "PANTRY_REDIS_DATA_DIR")"
  imports_data_dir="$(env_get_any "${env_file}" "$(default_data_root)/imports" "PANTRO_IMPORTS_DATA_DIR" "PANTRY_IMPORTS_DATA_DIR")"
  backups_data_dir="$(env_get_any "${env_file}" "$(default_data_root)/backups" "PANTRO_BACKUPS_DATA_DIR" "PANTRY_BACKUPS_DATA_DIR")"

  log_step "Updating .env"
  env_set "${env_file}" "PANTRO_VERSION" "${target_version}"
  env_set "${env_file}" "PANTRY_VERSION" "${target_version}"
  env_set "${env_file}" "PANTRO_IMAGE_NAMESPACE" "${image_namespace}"
  env_set "${env_file}" "PANTRY_IMAGE_NAMESPACE" "${image_namespace}"
  env_set "${env_file}" "PANTRO_POSTGRES_DATA_DIR" "${postgres_data_dir}"
  env_set "${env_file}" "PANTRO_REDIS_DATA_DIR" "${redis_data_dir}"
  env_set "${env_file}" "PANTRO_IMPORTS_DATA_DIR" "${imports_data_dir}"
  env_set "${env_file}" "PANTRO_BACKUPS_DATA_DIR" "${backups_data_dir}"
  env_set "${env_file}" "PANTRY_POSTGRES_DATA_DIR" "${postgres_data_dir}"
  env_set "${env_file}" "PANTRY_REDIS_DATA_DIR" "${redis_data_dir}"
  env_set "${env_file}" "PANTRY_IMPORTS_DATA_DIR" "${imports_data_dir}"
  env_set "${env_file}" "PANTRY_BACKUPS_DATA_DIR" "${backups_data_dir}"
  env_set "${env_file}" "BACKUP_STORAGE_ROOT" "$(env_get "${env_file}" "BACKUP_STORAGE_ROOT" "/var/lib/pantro/backups")"
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
  if [[ -x "${INSTALL_DIR}/healthcheck-pantro.sh" ]]; then
    "${INSTALL_DIR}/healthcheck-pantro.sh" --install-dir "${INSTALL_DIR}" --timeout 180
  else
    "${INSTALL_DIR}/healthcheck-pantry.sh" --install-dir "${INSTALL_DIR}" --timeout 180
  fi

  cat <<EOF

${PANTRO_COLOR_GREEN}Pantro update complete.${PANTRO_COLOR_RESET}
Current version: ${target_version}
Web URL: ${web_url}
API URL: ${api_url}

Useful commands:
  docker compose --env-file ${env_file} -f ${compose_file} ps
  docker compose --env-file ${env_file} -f ${compose_file} logs -f api
  docker compose --env-file ${env_file} -f ${compose_file} logs -f worker
EOF
}

main "$@"
