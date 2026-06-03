#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/web"

export COPYFILE_DISABLE=1

if lsof -nP -iTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 5173 is already in use. Stop the old web server first, or open http://127.0.0.1:5173."
  lsof -nP -iTCP:5173 -sTCP:LISTEN
  exit 1
fi

npm run dev
