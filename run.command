#!/bin/bash
# ORBIOS TACTICAL CONSOLE — UNIFIED RUNNER

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

echo "Terminating old ORBIOS processes..."
pkill -f dashboard_server.py
pkill -f panel_server.py
pkill -f orbios_sim.py
sleep 1

echo "Cleaning simulation signals..."
rm -rf signals/mission/* signals/logs/*
mkdir -p signals/mission signals/logs

# Compile C algorithm code if gcc is installed
if command -v gcc &> /dev/null; then
    echo "Compiling C algo code..."
    gcc -o algo_part/main2 algo_part/main2.c algo_part/payload.c
else
    echo "Warning: gcc not found, C algo compilation skipped (will rely on dynamic compile in simulator)."
fi

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
echo "  ORBIOS CONSOLE (FILE-BUS) RUNNING"
echo "  "
echo "  Main UI:    file://$PROJECT_DIR/index.html"
echo "  Dashboard:  http://127.0.0.1:5005"
echo "  Panel:      http://127.0.0.1:8765"
echo "------------------------------------------------"

# Automatically open index.html in the default browser on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Opening UI in default browser..."
    open "$PROJECT_DIR/index.html"
fi

# Keep alive and handle cleanup on exit
trap "echo 'Stopping ORBIOS servers...'; kill $DASH_PID $PANEL_PID $SIM_PID; exit" INT TERM
wait
