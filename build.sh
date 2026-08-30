#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export PYTHONUTF8=1
export PYTHONUNBUFFERED=1

on_error() {
    echo ""
    echo "============================================================"
    echo "  [ERROR] Build failed on line $1"
    echo "============================================================"
    echo ""
}
trap 'on_error $LINENO' ERR

echo ""
echo "============================================================"
echo "  MIYA Build System"
echo "============================================================"
echo ""
echo "  Use the interactive menu to build DSH and/or the Desktop app."
echo "  DSH Web runtime must be built before Electron (option [1] or [3])."
echo ""

PYTHON_BIN="python3"
if [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
fi

if [ "$#" -eq 0 ]; then
    "$PYTHON_BIN" scripts/build.py menu
else
    "$PYTHON_BIN" scripts/build.py "$@"
fi

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "============================================================"
    echo "  [ERROR] Build failed with exit code $EXIT_CODE"
    echo "============================================================"
    echo ""
    read -p "Press Enter to continue..."
else
    echo ""
    echo "============================================================"
    echo "  [OK] Build completed successfully"
    echo "============================================================"
    echo ""
fi
exit $EXIT_CODE
