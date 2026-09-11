#!/usr/bin/env bash
# Start the CareerDNA backend (port 8000) and frontend (port 5173) together.
# Ctrl+C stops both. Requires a prepared venv + node_modules (see README).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Pick the venv python regardless of OS.
if [ -x "$ROOT/backend/.venv/bin/python" ]; then
  PY="$ROOT/backend/.venv/bin/python"
elif [ -x "$ROOT/backend/.venv/Scripts/python.exe" ]; then
  PY="$ROOT/backend/.venv/Scripts/python.exe"
else
  echo "Backend venv not found. Run the backend setup from README first." >&2
  exit 1
fi

cleanup() {
  echo; echo "Stopping servers..."
  kill 0 2>/dev/null || true
}
trap cleanup EXIT

(cd "$ROOT/backend" && "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000) &
sleep 3
(cd "$ROOT/frontend" && npm run dev -- --host 0.0.0.0 --port 5173) &
wait
