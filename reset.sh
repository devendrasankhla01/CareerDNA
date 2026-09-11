#!/usr/bin/env bash
# Reset the CareerDNA demo database + evidence files to the freshly-seeded state.
# Safe to run while the API server is running.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -x "$ROOT/backend/.venv/bin/python" ]; then
  PY="$ROOT/backend/.venv/bin/python"
elif [ -x "$ROOT/backend/.venv/Scripts/python.exe" ]; then
  PY="$ROOT/backend/.venv/Scripts/python.exe"
else
  echo "Backend venv not found. Run the backend setup from README first." >&2
  exit 1
fi

(cd "$ROOT/backend" && "$PY" -m scripts.reset_demo)
