from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEV_STACK_SCRIPT = REPO_ROOT / "infra" / "scripts" / "dev-stack.sh"


def _prepare_sourced_script(tmp_path: Path) -> Path:
    temp_root = tmp_path / "repo"
    script_path = temp_root / "infra" / "scripts" / "dev-stack.sh"
    script_path.parent.mkdir(parents=True, exist_ok=True)

    script_text = DEV_STACK_SCRIPT.read_text()
    script_text = script_text.rsplit('main "$@"', 1)[0]
    script_path.write_text(script_text)
    return temp_root


def _run_bootstrap(tmp_path: Path, *, env: dict[str, str] | None = None) -> str:
    temp_root = _prepare_sourced_script(tmp_path)
    command = """
source "infra/scripts/dev-stack.sh"
bootstrap_dev_env
printf 'DEV_ENV_FILE=%s\n' "$DEV_ENV_FILE"
if [[ -n "${PANTRO_LOCAL_AI_API_KEY+x}" ]]; then
  printf 'PANTRO_LOCAL_AI_API_KEY=%s\n' "$PANTRO_LOCAL_AI_API_KEY"
else
  printf 'PANTRO_LOCAL_AI_API_KEY=<unset>\n'
fi
"""
    shell_env = {
        key: value
        for key, value in os.environ.items()
        if not (key.startswith("PANTRO_LOCAL_") or key.startswith("PANTRY_LOCAL_"))
    }
    completed = subprocess.run(
        ["bash", "-lc", command],
        cwd=temp_root,
        env={**shell_env, **(env or {})},
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def test_bootstrap_dev_env_prefers_dot_env_local_over_local_env_and_dot_env(tmp_path):
    temp_root = _prepare_sourced_script(tmp_path)
    (temp_root / ".env.local").write_text("PANTRO_LOCAL_AI_API_KEY=from-dot-env-local\n")
    (temp_root / "local.env").write_text("PANTRO_LOCAL_AI_API_KEY=from-local-env\n")
    (temp_root / ".env").write_text("PANTRO_LOCAL_AI_API_KEY=from-dot-env\n")

    output = subprocess.run(
        [
            "bash",
            "-lc",
            'source "infra/scripts/dev-stack.sh"; bootstrap_dev_env; printf "%s\\n" "$DEV_ENV_FILE"',
        ],
        cwd=temp_root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()

    assert output == str(temp_root / ".env.local")


def test_bootstrap_dev_env_only_forwards_explicit_legacy_local_bootstrap_vars(tmp_path):
    temp_root = _prepare_sourced_script(tmp_path)
    (temp_root / ".env.local").write_text("PANTRO_LOCAL_AI_API_KEY=from-dot-env-local\n")

    base_output = _run_bootstrap(tmp_path)
    assert "DEV_ENV_FILE=" + str(temp_root / ".env.local") in base_output
    assert "PANTRO_LOCAL_AI_API_KEY=<unset>" in base_output

    legacy_env = {"PANTRY_LOCAL_AI_API_KEY": "legacy-secret"}
    legacy_output = _run_bootstrap(tmp_path, env=legacy_env)
    assert "PANTRO_LOCAL_AI_API_KEY=legacy-secret" in legacy_output
