#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  launch_dashboard.command
#  Double-click this file in Finder to start the dashboard.
#  It will open automatically in your default browser.
#  To stop it, run stop_dashboard.command (or kill the PID in .dashboard.pid).
# ─────────────────────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")"

PID_FILE=".dashboard.pid"
LOG_FILE=".dashboard.log"
PORT=5000

# ── If already running, just open the browser ────────────────────────────────
if [ -f "$PID_FILE" ]; then
  SAVED_PID=$(cat "$PID_FILE")
  if kill -0 "$SAVED_PID" 2>/dev/null; then
    echo "Dashboard already running (PID $SAVED_PID)."
    echo "Opening browser..."
    open "http://127.0.0.1:$PORT"
    exit 0
  else
    echo "Stale PID file found — cleaning up."
    rm -f "$PID_FILE"
  fi
fi

# ── Check / install Python dependencies ──────────────────────────────────────
echo "Checking dependencies..."
MISSING=""
python3 -c "import flask"  2>/dev/null || MISSING="$MISSING flask"
python3 -c "import psutil" 2>/dev/null || MISSING="$MISSING psutil"
python3 -c "import yaml"   2>/dev/null || MISSING="$MISSING pyyaml"

if [ -n "$MISSING" ]; then
  echo "Installing:$MISSING"
  pip3 install $MISSING --break-system-packages 2>/dev/null \
    || pip3 install $MISSING
fi

# ── Read configured port from YAML (simple grep, no Python needed here) ──────
YAML_PORT=$(grep -A2 '^server:' dashboard_config.yaml \
            | grep 'port:' | awk '{print $2}' | tr -d '"' | head -1)
[ -n "$YAML_PORT" ] && PORT=$YAML_PORT

# ── Start the server in the background ───────────────────────────────────────
echo "Starting dashboard server on port $PORT..."
nohup python3 dashboard_server.py > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
SERVER_PID=$(cat "$PID_FILE")

# ── Wait for server to be ready ──────────────────────────────────────────────
echo "Waiting for server..."
for i in $(seq 1 15); do
  if curl -sf "http://127.0.0.1:$PORT/config" > /dev/null 2>&1; then
    break
  fi
  sleep 0.4
done

# ── Open browser ─────────────────────────────────────────────────────────────
echo "Opening http://127.0.0.1:$PORT in Firefox..."

/Applications/Firefox.app/Contents/MacOS/firefox --new-window "http://127.0.0.1:$PORT" &
sleep 2
osascript -e 'tell application "Firefox" to set bounds of front window to {0, 0, 1500, 200}'

echo ""
echo "─────────────────────────────────────────────"
echo "  Dashboard running at http://127.0.0.1:$PORT"
echo "  PID: $SERVER_PID"
echo "  Log: $(pwd)/$LOG_FILE"
echo "  Run stop_dashboard.command to stop."
echo "─────────────────────────────────────────────"
