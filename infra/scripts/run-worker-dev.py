#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from watchfiles import PythonFilter, run_process

ROOT_DIR = Path("/workspace")
WATCH_PATHS = (
    ROOT_DIR / "apps/api/app",
    ROOT_DIR / "apps/api/alembic",
    ROOT_DIR / "apps/worker/worker",
)


def run_worker() -> int:
    os.environ["APP_VERSION"] = (ROOT_DIR / "VERSION").read_text(encoding="utf-8").strip()
    completed = subprocess.run([sys.executable, "-m", "worker.main"], check=False)
    return completed.returncode


if __name__ == "__main__":
    run_process(*(str(path) for path in WATCH_PATHS), target=run_worker, watch_filter=PythonFilter())
