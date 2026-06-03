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

if lsof -nP -iTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 5173 is already in use. Stop the old web server first, or open http://127.0.0.1:5173."
  lsof -nP -iTCP:5173 -sTCP:LISTEN
  exit 1
fi

PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

if [[ ! -d "$ROOT/web/node_modules" ]]; then
  echo "Installing web dependencies..."
  (cd "$ROOT/web" && npm install)
fi

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${WEB_PID:-}" ]]; then
    kill "$WEB_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting backend: http://127.0.0.1:8000"
PYTHONPATH="$ROOT" "$PYTHON" -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

echo "Starting web UI: http://127.0.0.1:5173"
(cd "$ROOT/web" && npm run dev) &
WEB_PID=$!

echo
echo "Open http://127.0.0.1:5173"
echo "Press Ctrl+C to stop both services."

while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    wait "$BACKEND_PID"
    exit $?
  fi
  if ! kill -0 "$WEB_PID" 2>/dev/null; then
    wait "$WEB_PID"
    exit $?
  fi
  sleep 1
done
