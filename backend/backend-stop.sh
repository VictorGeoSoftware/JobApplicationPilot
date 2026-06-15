#!/usr/bin/env bash
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$BACKEND_DIR/.backend.pid"

cd "$BACKEND_DIR"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No PID file found. Backend may already be stopped."
else
  PID="$(cat "$PID_FILE")"
  if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
    echo "Stopping backend (PID: $PID)..."
    kill "$PID" 2>/dev/null || true

    for _ in {1..20}; do
      if kill -0 "$PID" 2>/dev/null; then
        sleep 0.2
      else
        break
      fi
    done

    if kill -0 "$PID" 2>/dev/null; then
      echo "Force stopping backend (PID: $PID)..."
      kill -9 "$PID" 2>/dev/null || true
    fi

    pkill -P "$PID" 2>/dev/null || true
    echo "Backend stopped."
  else
    echo "Stale PID file found. Cleaning up."
  fi

  rm -f "$PID_FILE"
fi

echo "Cleaning Python cache folders..."
find "$BACKEND_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +

echo "Done."
