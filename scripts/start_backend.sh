#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export COPYFILE_DISABLE=1
find atom_locator backend scripts -name '._*' -delete 2>/dev/null || true

if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8000 is already in use. Stop the old backend first, or open the already-running app."
  lsof -nP -iTCP:8000 -sTCP:LISTEN
  exit 1
fi

PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

PYTHONPATH="$ROOT" "$PYTHON" -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
