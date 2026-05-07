#!/bin/bash
set -e
cd "$(dirname "$0")/.."

PID_FILE=".dashboard.pid"
LOG_FILE=".dashboard.log"
PORT=5005

# Start server using uv
echo "Starting ORBIOS Space OS on port $PORT..."
PYTHONPATH=. nohup uv run src/server/main.py > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
SERVER_PID=$(cat "$PID_FILE")

echo "Waiting for server..."
sleep 2

# Open browser (Universal)
if [[ "$OSTYPE" == "darwin"* ]]; then
  open "http://127.0.0.1:$PORT"
else
  xdg-open "http://127.0.0.1:$PORT" || echo "Please open http://127.0.0.1:$PORT manually."
fi

echo "─────────────────────────────────────────────"
echo "  ORBIOS TACTICAL CONSOLE RUNNING"
echo "  URL: http://127.0.0.1:$PORT"
echo "  PID: $SERVER_PID"
echo "─────────────────────────────────────────────"
