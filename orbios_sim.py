#!/usr/bin/env python3
import os
import time
import json
import pathlib
import random
from datetime import datetime
from skyfield.api import load, wgs84, EarthSatellite

# --- Paths ---
PROJECT_ROOT = pathlib.Path(__file__).parent.absolute()
SIGNALS      = PROJECT_ROOT / "signals"
DATA         = PROJECT_ROOT / "data"
MISSION      = SIGNALS / "mission"
LOGS         = SIGNALS / "logs"

# Ensure directories exist
for p in [MISSION, LOGS, DATA / "telemetry"]:
    p.mkdir(parents=True, exist_ok=True)

# --- Orbital Setup ---
# ISS (ZARYA) TLE - Used as our primary sensor platform for the PoC
tle_line1 = '1 25544U 98067A   24124.52622410  .00016717  00000-0  30142-3 0  9997'
tle_line2 = '2 25544  51.6405 186.6817 0004128  63.5356 345.8646 15.49845924451993'
ts_field = load.timescale()
satellite = EarthSatellite(tle_line1, tle_line2, 'ORBIOS-S1', ts_field)

def log_event(msg, payload=None):
    ts_str = time.strftime("%H:%M:%S")
    print(f"[{ts_str}] {msg}")
    log_name = f"{ts_str}_{msg.replace(' ', '_')}"
    log_path = LOGS / log_name
    
    data = {"timestamp": ts_str, "message": msg, "payload": payload or {}}
    with open(log_path, "w") as f:
        json.dump(data, f)

def update_telemetry():
    t = ts_field.now()
    geocentric = satellite.at(t)
    subpoint = wgs84.subpoint(geocentric)
    
    telemetry = {
        "id": "ORBIOS-S1",
        "lat": subpoint.latitude.degrees,
        "lon": subpoint.longitude.degrees,
        "alt_km": subpoint.elevation.km,
        "timestamp": datetime.now().isoformat()
    }
    
    with open(DATA / "telemetry" / "sat_01.json", "w") as f:
        json.dump(telemetry, f)
    return telemetry

def clean_signals():
    for f in MISSION.iterdir(): f.unlink()
    for f in LOGS.iterdir(): f.unlink()

def run_sim():
    log_event("ORBIOS SIMULATOR ONLINE")
    
    while True:
        try:
            # 1. Update Physics
            sat_data = update_telemetry()
            
            # 2. Check for commands
            found_files = list(MISSION.iterdir())
            for f in found_files:
                fname = f.name
                
                if fname.startswith("INIT_FIRE"):
                    # Generate a fire at a random location near the satellite's path
                    fire_data = {
                        "type": "HEAT_ANOMALY",
                        "lat": sat_data["lat"] + random.uniform(-2, 2),
                        "lon": sat_data["lon"] + random.uniform(-2, 2),
                        "intensity": random.uniform(0.7, 0.95),
                        "status": "DETECTED"
                    }
                    log_event("DETECTION: HEAT ANOMALY DETECTED", fire_data)
                    with open(MISSION / "HEAT_SPIKE_ACTIVE.json", "w") as jf:
                        json.dump(fire_data, jf)
                    f.unlink()

                elif fname.startswith("START_AI"):
                    log_event("AI_AGENT: INITIATING INFERENCE")
                    time.sleep(2)
                    # Read the active fire data
                    if (MISSION / "HEAT_SPIKE_ACTIVE.json").exists():
                        with open(MISSION / "HEAT_SPIKE_ACTIVE.json", "r") as rj:
                            fire_data = json.load(rj)
                        fire_data["status"] = "CONFIRMED"
                        log_event("AI_AGENT: WILDFIRE CONFIRMED", fire_data)
                        with open(MISSION / "FIRE_CONFIRMED.json", "w") as jf:
                            json.dump(fire_data, jf)
                        (MISSION / "HEAT_SPIKE_ACTIVE.json").unlink()
                    f.unlink()
                    
                elif fname.startswith("RESET"):
                    log_event("SYSTEM RESET COMMAND RECEIVED")
                    clean_signals()
                    log_event("ORBIOS SIMULATOR ONLINE")
            
            time.sleep(0.5)
        except Exception as e:
            print(f"Sim Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    try:
        run_sim()
    except KeyboardInterrupt:
        log_event("SIMULATOR STOPPED")
