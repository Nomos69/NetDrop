#!/usr/bin/env bash
# Double-click this file in a Linux file manager (choose Run) after setup.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]]; then
  echo "NetDrop is not set up yet. Follow README.md once, then run this launcher again."
  read -r -p "Press Enter to close..." _
  exit 1
fi

.venv/bin/python -m app.main &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT INT TERM
sleep 1

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open http://127.0.0.1:8000 >/dev/null 2>&1 &
fi

echo "NetDrop is running. Keep this window open while people share files."
wait "$server_pid"
