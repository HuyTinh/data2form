#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"

if [[ -x "$ROOT_DIR/venv/Scripts/python.exe" ]]; then
  PYTHON_BIN="$ROOT_DIR/venv/Scripts/python.exe"
elif [[ -x "$ROOT_DIR/venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/venv/bin/python"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
else
  printf 'Python was not found. Create a virtual environment and install requirements.txt first.\n' >&2
  exit 1
fi

DEV_SCRIPT="$SCRIPT_DIR/dev.py"
if command -v cygpath >/dev/null 2>&1; then
  DEV_SCRIPT="$(cygpath -m "$DEV_SCRIPT")"
fi
exec "$PYTHON_BIN" "$DEV_SCRIPT" "$@"
