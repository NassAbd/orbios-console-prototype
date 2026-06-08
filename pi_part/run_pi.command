#!/bin/bash
# ORBIOS TACTICAL CONSOLE — RASPBERRY PI RUNNER

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

echo "Terminating old ORBIOS processes on Pi..."
pkill -f orbios_sim.py
sleep 1

echo "Cleaning simulation signals on Pi..."
rm -rf signals/mission/* signals/logs/*
mkdir -p signals/mission signals/logs

# Compile C algorithm code natively
if command -v gcc &> /dev/null; then
    echo "Compiling C algo code natively on Pi..."
    gcc -o algo_part/main2 algo_part/main2.c algo_part/payload.c
else
    echo "Warning: gcc not found, C algo compilation skipped."
fi

echo "------------------------------------------------"
echo "  ORBIOS SIMULATION DAEMON & API SERVER"
echo "  Running on Raspberry Pi"
echo "  Listening on: http://0.0.0.0:5006"
echo "------------------------------------------------"

# Start the simulation daemon (which also starts the API server)
uv run python3 orbios_sim.py
