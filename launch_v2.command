#!/bin/bash
# ORBIOS TACTICAL CONSOLE V2 — LAUNCHER (CLEAN REBOOT)

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

echo "Terminating old ORBIOS processes..."
pkill -f dashboard_server.py
pkill -f panel_server.py
pkill -f orbios_sim.py
sleep 1

echo "Cleaning signals..."
rm -rf signals/mission/* signals/logs/*
mkdir -p signals/mission signals/logs

# Start DashBoard (Port 5005)
uv run python3 dashboard_server.py > .dashboard_v2.log 2>&1 &
DASH_PID=$!

# Start Control Panel (Port 8765)
uv run python3 panel_server.py > .panel_v2.log 2>&1 &
PANEL_PID=$!

# Start Signal Simulator
uv run python3 orbios_sim.py > .sim_v2.log 2>&1 &
SIM_PID=$!

echo "------------------------------------------------"
echo "  ORBIOS CONSOLE V2 (FILE-BUS) RUNNING"
echo "  "
echo "  Main UI:    file://$PROJECT_DIR/index.html"
echo "  Dashboard:  http://127.0.0.1:5005"
echo "  Panel:      http://127.0.0.1:8765"
echo "------------------------------------------------"
echo "Please open index.html in FIREFOX."

# Keep alive and handle cleanup
trap "kill $DASH_PID $PANEL_PID $SIM_PID; exit" INT TERM
wait
