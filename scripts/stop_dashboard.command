#!/bin/bash
cd "$(dirname "$0")/.."
PID_FILE=".dashboard.pid"
PORT=5005

function kill_by_port() {
  local port=$1
  local pid=$(lsof -t -i :$port)
  if [ -n "$pid" ]; then
    echo "Found ORBIOS process on port $port (PID $pid). Terminating..."
    kill $pid
    return 0
  fi
  return 1
}

if [ -f "$PID_FILE" ]; then
  SAVED_PID=$(cat "$PID_FILE")
  if kill -0 "$SAVED_PID" 2>/dev/null; then
    kill "$SAVED_PID"
    rm -f "$PID_FILE"
    echo "ORBIOS Space OS stopped (PID $SAVED_PID)."
    exit 0
  fi
  rm -f "$PID_FILE"
fi

if kill_by_port $PORT; then
  echo "ORBIOS Space OS stopped via port lookup."
else
  echo "No ORBIOS process found running on port $PORT."
fi
