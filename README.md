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

```
orbios_prototype/
├── workstation_part/           # Ground station/workstation UI & servers
│   ├── dashboard_server.py     # Telemetry HTTP API & static file hosting
│   ├── panel_server.py         # HTTP Control Panel server
│   ├── index.html              # Unified Dashboard Cockpit interface
│   ├── simulator.html          # Map-only simulation viewer (remote mode)
│   ├── tactical_map.html       # Leaflet maps and footprint viewer
│   ├── dashboard.html          # System Monitor top rail UI
│   ├── panel.html              # LCD Control Panel UI
│   ├── panel_config.json       # Control button definitions
│   ├── dashboard_config.yaml   # Temperature and telemetry limits
│   ├── schema.py               # Pydantic validation schemas
│   └── run.command             # Station unified runner script
│
├── pi_part/                    # Simulation & execution on the Raspberry Pi
│   ├── orbios_sim.py           # Simulation telemetry & signal-clearing daemon
│   ├── run_pi.command          # Pi daemon startup script
│   ├── schema.py               # Shared data schemas
│   ├── algo_part/              # Edge detection C code
│   │   ├── main2.c
│   │   ├── payload.c & payload.h
│   │   ├── input.csv
│   │   └── output/             # Output folder for detected alerts (.dat)
│   ├── signals/                # Inter-process coordination folder
│   └── data/                   # Generated telemetry storage
│
├── tests/                      # Pytest automation suite
│   ├── test_simulation.py
│   └── test_remote.py
│
├── pyproject.toml              # Workstation project configuration
├── uv.lock                     # Lockfile
└── README.md
```

---

## 🚀 How to Run & Test

### 1. Prerequisites
Ensure you have the Python virtual environment manager `uv` installed. If missing, run:
```bash
curl -sSf https://get.uv.dev | sh
```

### 2. Operational Modes

#### Option A: Running Locally (All-in-One Mock Mode)
To run both the ground station console and the simulation loop on your local machine:
```bash
cd workstation_part/
./run.command
```
This script will:
* Boot the telemetry server (`localhost:5005`), panel server (`localhost:8765`), and simulator daemon under local environment wrappers (`uv run`).
* Serve all HTML templates via HTTP to prevent cross-origin (`CORS`) file access restrictions.
* **Automatically open the dashboard UI (`index.html`) in your default web browser.**

#### Option B: Distributed Remote Mode (Raspberry Pi + Workstation)
To run the simulation and C algorithm on the Raspberry Pi, and stream metrics/control commands from the ground station workstation:

1. **On the Raspberry Pi (`192.168.2.2`):**
   Copy the `pi_part/` folder to the Pi, then start the daemon:
   ```bash
   cd pi_part/
   ./run_pi.command
   ```

2. **On the Workstation (Debian VNC Session):**
   Run the workstation console specifying the Pi's IP address:
   ```bash
   cd workstation_part/
   ./run.command --remote 192.168.2.2
   ```
   * This opens the standalone cockpit Console and the Simulator map, automatically proxying requests to the Pi daemon.

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
* Go to the terminal window where the runner is active and press **`Ctrl + C`**. All background Python daemons will be killed automatically.

