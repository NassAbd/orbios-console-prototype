# OrbiOS Tactical Console — Wildfire Detection PoC (V2)

An ultra-responsive, signal-driven space tactical operations cockpit designed for satellite monitoring and wildfire anomaly edge-classification. This Proof of Concept (PoC) leverages a high-fidelity **Distributed File-Bus Architecture** where independent telemetry rails, tactical geospatial screens, and industrial command panels coordinate asynchronously through localized filesystem state signals.

---

## 🎯 PoC Objective

The core goal of this prototype is to demonstrate a mission-critical tactical console split into three logical views, orchestrating complex orbital sensor tasks without centralized direct database/API state coupling:
1. **System Monitor (Top Window)**: Live hardware metrics and automated system-wide critical alerts.
2. **Tactical Geospatial (Center-Left Window)**: Real-time satellite propagation tracker using high-precision orbital physics (Skyfield), complete with coverage footprints and dynamic hazard visualization.
3. **Control Panel (Center-Right Window)**: Hardware-styled command console simulating physical buttons, toggles, and direct terminal logging.

---

## 🛰️ Operational Concept (CONOPS) & Features

### 📡 Store-and-Forward Downlink Buffering
The satellite can operate in disconnected environments. This PoC implements realistic orbital communications constraints using **Acquisition of Signal (AOS)** handshakes:
* **Direct Transmission**: With **AOS GS-01** active, raw sensor pings and AI edge results stream straight to Earth in real-time, instantly rendering alerts and visual hazard loops on the map.
* **Onboard Buffering (Store-and-Forward)**: When **AOS GS-01** is offline (disconnected), sensor detections and AI-confirmed classifications are securely queued inside the satellite's onboard registers. The Earth interfaces remain clean and silent. The exact millisecond the connection link is restored, the buffered queue flushes to the ground, triggering high-intensity map visuals and flashing warning alerts on the system dashboard.

---

## 📂 Project Structure

```bash
orbios_prototype/
├── index.html                  # Main Cockpit Wrapper (tiles the 3 sub-windows via iframes)
├── launch_v2.command           # Entrypoint launcher script (coordinates & boots the architecture)
├── orbios_sim.py               # Satellite Simulator (handles Skyfield physics, logic & buffering)
│
├── dashboard_server.py         # Flask telemetry backend (serves localhost:5005 & CORS file gateway)
├── dashboard_config.yaml       # Telemetry thresholds and component settings
├── dashboard.html              # System Monitor Top Rail UI (flashes emergency-red on alerts)
│
├── panel_server.py             # HTTP Control Panel server (handles localhost:8765 filesystem api)
├── panel_config.json           # Interactive Button and register mapping definitions
├── panel.html                  # Control Panel frontend (simulates physical LCD + buttons)
│
├── tactical_map.html           # Geospatial Leaflet map (renders satellite footprint, markers & popups)
│
├── signals/                    # THE FILE-BUS (Inter-process nervous system)
│   ├── mission/                # Active signals (e.g. INIT_FIRE, START_AI, AOS_GS01.dat)
│   └── logs/                   # Dynamic operational log files read by the Panel LCD Screen
│
├── data/
│   └── telemetry/              # Live computed orbital coordinates (sat_01.json)
│
├── base_resources/             # Legacy reference files (preserved & untouched)
└── v1_centralized/             # Archive of the previous monolithic version (V1)
```

---

## 🚀 How to Run & Test

### 1. Prerequisites
Ensure you have the Python virtual environment manager `uv` installed. If missing, run:
```bash
curl -sSf https://get.uv.dev | sh
```

### 2. Boot the Console
From the project directory, execute the interactive launch command:
```bash
bash launch_v2.command
```
This script will:
* Terminate any lingering port bindings.
* Purge stale filesystem cues.
* Boot the telemetry server (`localhost:5005`), panel server (`localhost:8765`), and simulator daemon under local isolated environment wrappers (`uv run`).

### 3. Open the Interface
Open **Firefox** and navigate to:
```
file:///path/to/cloned/repo/orbios_prototype/index.html
```

---

## 🕹️ Demonstration Scenarios

### Scenario A: Delayed Downlink (Buffered Queue) — *Highly Recommended for Showcases*
1. **Prepare**: Verify **AOS GS-01 (BTN 05)** is **OFF** (the button is dark gray, indicating no communication signal).
2. **Scan**: Click **TRIGGER FIRE (BTN 03)**.
   * *Observation*: The Control Panel logs `STORED ONBOARD (LINK OFFLINE)`. The tactical map remains completely silent and the satellite footprint travels empty.
3. **Analyze**: Click **RUN AI ENGINE (BTN 04)**.
   * *Observation*: The onboard system finishes edge processing. The screen logs `WILDFIRE CONFIRMED - STORED`. Ground units are still completely unaware (map and top dashboard remain normal).
4. **Establish Link**: Turn **AOS GS-01 (BTN 05)** **ON** (toggles to latched Amber).
   * *Result*: **Instant Uplink Trigger!** The buffered alert drops onto the Earth terminal. The map immediately flies to the threat location, rendering a high-intensity pulsing crimson wildfire circle, and the top cockpit rail triggers flashing neon-red emergency alarms.

### Scenario B: Real-Time Stream
1. Latch **AOS GS-01 (BTN 05)** **ON** first.
2. Press **TRIGGER FIRE (BTN 03)**.
   * *Result*: Direct downlink streams raw amber indicators with tooltips directly onto the map.
3. Press **RUN AI ENGINE (BTN 04)**.
   * *Result*: After 2 seconds of edge calculation, the hazard turns to critical red, displaying live threat statistics and initiating flashing cockpit alarms.
4. Press **PURGE SIGNALS (BTN 06)** or **RESET (BTN 01)** to wipe files and reset the simulator back to base orbital tracking.

---

## 🛑 How to Stop
To shut down the entire V2 server loop gracefully:
* Go to the shell terminal where `launch_v2.command` is running and press **`Ctrl + C`**. All background daemons will be killed automatically.
