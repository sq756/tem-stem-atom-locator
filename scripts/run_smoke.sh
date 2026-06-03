#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export COPYFILE_DISABLE=1
find atom_locator backend scripts -name '._*' -delete 2>/dev/null || true

PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

PYTHONPATH="$ROOT" "$PYTHON" -m compileall atom_locator backend
PYTHONPATH="$ROOT" "$PYTHON" scripts/smoke_test.py
cd web
npm run build
