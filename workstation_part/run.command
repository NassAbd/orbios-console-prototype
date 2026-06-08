#!/bin/bash
# ORBIOS TACTICAL CONSOLE — UNIFIED RUNNER

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

# Parse arguments
REMOTE_IP=""
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --remote) REMOTE_IP="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

echo "Terminating old ORBIOS processes..."
pkill -f dashboard_server.py
pkill -f panel_server.py
pkill -f orbios_sim.py
sleep 1

if [ -n "$REMOTE_IP" ]; then
    echo "Running in REMOTE Mode (connecting to Pi at $REMOTE_IP)..."
    
    # On repasse uniquement l'IP brute, le code Python gère le reste
    # Start DashBoard (Port 5005) in remote proxy mode
    uv run python3 dashboard_server.py --remote "$REMOTE_IP" > .dashboard_v2.log 2>&1 &
    DASH_PID=$!
    
    # Start Control Panel (Port 8765) in remote proxy mode
    uv run python3 panel_server.py --remote "$REMOTE_IP" > .panel_v2.log 2>&1 &
    PANEL_PID=$!
    
    # Wait a moment for servers to bind and validate connection
    sleep 2
    
    # Check if servers started successfully
    if ! kill -0 $DASH_PID &>/dev/null || ! kill -0 $PANEL_PID &>/dev/null; then
        echo "ERROR: Failed to start workstation servers."
        echo "--> Regarde le contenu de .dashboard_v2.log et .panel_v2.log pour voir l'erreur Python."
        kill $DASH_PID $PANEL_PID 2>/dev/null
        exit 1
    fi
    
    echo "------------------------------------------------"
    echo "  ORBIOS CONSOLE RUNNING IN REMOTE PROXY MODE"
    echo "  Connecting to Raspberry Pi at: $REMOTE_IP"
    echo "  "
    echo "  1. Console Dashboard: http://localhost:5005"
    echo "  2. Simulation view:   http://localhost:5005/simulator.html"
    echo "------------------------------------------------"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Opening both Console and Simulator windows..."
        open "http://localhost:5005"
        open "http://localhost:5005/simulator.html"
    fi
    
    trap "echo 'Stopping ORBIOS proxy servers...'; kill $DASH_PID $PANEL_PID; exit" INT TERM
    wait
else
    echo "Running in LOCAL Mode..."
    
    echo "Cleaning simulation signals..."
    rm -rf ../pi_part/signals/mission/* ../pi_part/signals/logs/*
    mkdir -p ../pi_part/signals/mission ../pi_part/signals/logs
    
    if command -v gcc &> /dev/null; then
        echo "Compiling C algo code..."
        gcc -o ../pi_part/algo_part/main2 ../pi_part/algo_part/main2.c ../pi_part/algo_part/payload.c
    else
        echo "Warning: gcc not found, C algo compilation skipped."
    fi
    
    uv run python3 dashboard_server.py > .dashboard_v2.log 2>&1 &
    DASH_PID=$!
    
    uv run python3 panel_server.py > .panel_v2.log 2>&1 &
    PANEL_PID=$!
    
    (cd ../pi_part && uv run python3 orbios_sim.py > .sim_v2.log 2>&1 &)
    SIM_PID=$!

    echo "------------------------------------------------"
    echo "  ORBIOS CONSOLE RUNNING IN LOCAL MODE"
    echo "  "
    echo "  Main UI:    http://localhost:5005/index.html"
    echo "  Dashboard:  http://localhost:5005"
    echo "  Panel:      http://localhost:8765"
    echo "------------------------------------------------"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Opening local UI in default browser..."
        open "http://localhost:5005/index.html"
    fi
    
    trap "echo 'Stopping ORBIOS local servers...'; kill $DASH_PID $PANEL_PID $SIM_PID; exit" INT TERM
    wait
fi
