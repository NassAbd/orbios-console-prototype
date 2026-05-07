#!/bin/bash
# ─────────────────────────────────────────────
#  stop_dashboard.command
#  Double-click to stop the running dashboard.
# ─────────────────────────────────────────────

cd "$(dirname "$0")"

PID_FILE=".dashboard.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "No dashboard PID file found — is it running?"
  exit 0
fi

SAVED_PID=$(cat "$PID_FILE")

if kill -0 "$SAVED_PID" 2>/dev/null; then
  kill "$SAVED_PID"
  rm -f "$PID_FILE"
  echo "Dashboard stopped (was PID $SAVED_PID)."
else
  echo "Process $SAVED_PID is not running. Cleaning up stale PID file."
  rm -f "$PID_FILE"
fi
