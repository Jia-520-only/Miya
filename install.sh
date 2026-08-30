#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export PYTHONUTF8=1
export PYTHONUNBUFFERED=1
export PIP_DISABLE_PIP_VERSION_CHECK=1

PYTHON_BIN="python3"
if [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1 && [ ! -x "$PYTHON_BIN" ]; then
    echo "[ERROR] Python 3.11 or newer is required." >&2
    exit 1
fi

exec "$PYTHON_BIN" setup/scripts/install.py "$@"
