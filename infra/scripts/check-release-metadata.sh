#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CURRENT_VERSION="$(tr -d '[:space:]' < "${ROOT_DIR}/VERSION")"
REPOSITORY="${1:-${RELEASE_CHECK_REPOSITORY:-RoBro92/pantry}}"

METADATA_URL="https://api.github.com/repos/${REPOSITORY}/releases/latest"

python3 - "${CURRENT_VERSION}" "${METADATA_URL}" <<'PY'
import json
import sys
import urllib.request

current_version = sys.argv[1]
metadata_url = sys.argv[2]

with urllib.request.urlopen(metadata_url, timeout=5) as response:
    payload = json.load(response)

tag = str(payload.get("tag_name") or "").strip()
latest_version = tag[1:] if tag.lower().startswith("v") else tag
update_available = bool(latest_version and latest_version != current_version)

print(f"current_version={current_version}")
print(f"latest_version={latest_version or 'unknown'}")
print(f"release_tag={tag or 'unknown'}")
print(f"update_available={'true' if update_available else 'false'}")
print(f"release_notes_url={payload.get('html_url') or ''}")
PY
