#!/usr/bin/env bash
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$BACKEND_DIR/.venv"
PID_FILE="$BACKEND_DIR/.backend.pid"
LOG_FILE="$BACKEND_DIR/.backend.log"

if [[ -f "$PID_FILE" ]]; then
  EXISTING_PID="$(cat "$PID_FILE")"
  if [[ -n "$EXISTING_PID" ]] && kill -0 "$EXISTING_PID" 2>/dev/null; then
    echo "Backend already running (PID: $EXISTING_PID)."
    echo "Log file: $LOG_FILE"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

cd "$BACKEND_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating virtual environment..."
  if command -v python3.12 >/dev/null 2>&1; then
    python3.12 -m venv .venv
  else
    python3 -m venv .venv
  fi
fi

source "$VENV_DIR/bin/activate"

echo "Installing/updating dependencies..."
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt >/dev/null

echo "Starting backend..."
nohup python run.py >"$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"

sleep 1
if kill -0 "$NEW_PID" 2>/dev/null; then
  echo "Backend started (PID: $NEW_PID)."
  echo "Health: http://localhost:8000/api/health"
  echo "Log file: $LOG_FILE"
else
  echo "Failed to start backend. Check: $LOG_FILE"
  rm -f "$PID_FILE"
  exit 1
fi
