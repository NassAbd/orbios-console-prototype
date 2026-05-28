# OrbiOS Tactical Console — Wildfire & Oil Leak Detection PoC

An ultra-responsive, signal-driven space tactical operations cockpit designed for satellite monitoring and wildfire/oil leak anomaly edge-classification. This Proof of Concept (PoC) leverages a high-fidelity **Distributed File-Bus Architecture** where independent telemetry rails, tactical geospatial screens, and industrial command panels coordinate asynchronously through localized filesystem state signals.

---

## 🎯 PoC Objective

The core goal of this prototype is to demonstrate a mission-critical tactical console split into three logical views, orchestrating complex orbital sensor tasks:
1. **System Monitor (Top Window)**: Live hardware metrics and automated system-wide critical alerts.
2. **Tactical Geospatial (Center-Left Window)**: Real-time satellite propagation tracker focused statically over the Spain/Portugal region, showing dynamic hazard popup notifications.
3. **Control Panel (Center-Right Window)**: Hardware-styled command console simulating physical buttons, toggles, and direct terminal logging.

---

## 🛰️ Operational Concept (CONOPS) & Features

### 📡 Direct Downlink & Static Footprint
* **Static Footprint Focus:** The satellite orbit is configured to remain stationary over the Spain/Portugal sector (Latitude: `40.2000` N, Longitude: `-7.8000` E, Altitude: `420` km), allowing constant and focused surveillance of high-risk regions.
* **Direct Telemetry Downlink:** Detections are downlinked directly from the satellite to the ground station in real-time. No manual AOS (Acquisition of Signal) connection step is needed.
* **Transient Visual Alerts (3-Second Expiration):** To ensure a dynamic and uncluttered map view, wildfire and oil leak visual alert popups are automatically cleared/dismissed from the screen exactly 3 seconds after they are received.
* **Emergency Dashboard Warning:** When a critical hazard is active, the System Monitor cockpit rail flashes neon red with a simplified message: `⚡ CRITICAL WARNING ⚡`.

---

## 📂 Project Structure

```bash
orbios_prototype/
├── index.html                  # Main Cockpit Wrapper (tiles the 3 sub-windows via iframes)
├── run.command                 # Unified launcher script (pre-compiles C code, runs servers, launches UI)
├── orbios_sim.py               # Satellite Simulator (tracks active alert timers, unlinks expired alerts)
│
├── dashboard_server.py         # Flask telemetry backend (serves localhost:5005 & CORS file gateway)
├── dashboard_config.yaml       # Telemetry thresholds and component settings
├── dashboard.html              # System Monitor Top Rail UI (flashes emergency-red with critical warnings)
│
├── panel_server.py             # HTTP Control Panel server (handles localhost:8765 filesystem api)
├── panel_config.json           # Interactive Button and register mapping definitions
├── panel.html                  # Control Panel frontend (simulates physical LCD + buttons)
│
├── tactical_map.html           # Geospatial Leaflet map (renders satellite footprint and transient popups)
│
├── signals/                    # THE FILE-BUS (Inter-process nervous system)
│   ├── mission/                # Active signals (e.g. START_AI, RESET, FIRE_CONFIRMED.json)
│   └── logs/                   # Dynamic operational log files read by the Panel LCD Screen
│
├── data/
│   └── telemetry/              # Live computed orbital coordinates (sat_01.json)
│
├── algo_part/                  # C-PIPELINE ALGORITHM
│   ├── call1/                  # Pre-processing and post-processing mock .dat files
│   ├── input.csv               # Raw sensor data read by the C program
│   ├── main2.c                 # C entrypoint simulating satellite OS pre/post-processing files
│   ├── payload.c & payload.h   # C edge inference risk-scoring logic
│   └── output/                 # Folder where C program writes detected hazard .dat files
│
└── tests/
    └── test_simulation.py      # Automated Pytest suite checking coordinates and 3s expiration logic
```

---

## 🚀 How to Run & Test

### 1. Prerequisites
Ensure you have the Python virtual environment manager `uv` installed. If missing, run:
```bash
curl -sSf https://get.uv.dev | sh
```

### 2. Boot the Console & Open the UI
From the project root directory, run the unified executable command:
```bash
./run.command
```
This script will:
* Terminate any lingering port bindings on ports 5005 and 8765.
* Purge stale filesystem cues in `signals/`.
* Pre-compile the C algorithm source code into `algo_part/main2` using `gcc`.
* Boot the telemetry server (`localhost:5005`), panel server (`localhost:8765`), and simulator daemon under local isolated environment wrappers (`uv run`).
* **Automatically open the dashboard UI (`index.html`) in your default web browser.**

---

## 🕹️ Demonstration Scenarios

### Scenario A: Running the Edge Detection Pipeline
1. Click the **RUN DEMO** button on the Control Panel (Button 4).
2. Observe the Control Panel logging each preprocessing step chronologically (`Ephemeris signal reception`, `Real time position tracking`, etc.).
3. Watch the map view:
   - When the edge-AI processes a wildfire or oil leak from the C pipeline, a details popup box directly opens on the map at the threat coordinates.
   - After exactly 3 seconds, the popup vanishes cleanly as the simulator deletes the expired alert signal.
   - Meanwhile, the top System Monitor flashes neon red displaying `⚡ CRITICAL WARNING ⚡`.

### Scenario B: Resetting/Purging the Demo
1. Press the **PURGE SIGNALS** button on the Control Panel (Button 6) at any point during execution.
2. The running C program process is terminated instantly, all log files are deleted, active map popups are cleared, and the cockpit transitions back to a clean `IDLE` state.

---

## 🛑 How to Stop
To shut down all running servers gracefully:
* Go to the terminal window where `./run.command` is active and press **`Ctrl + C`**. All background Python daemons will be killed automatically.

