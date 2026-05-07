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

# --- Onboard Memory Buffer State ---
STATE = {
    "onboard_anomaly": None,     # Unconfirmed raw sensor logs
    "onboard_confirmed": None    # Confirmed AI wildfire logs
}

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
    STATE["onboard_anomaly"] = None
    STATE["onboard_confirmed"] = None

def is_aos_active():
    """Check if the Ground Station AOS (Acquisition of Signal) connection is established"""
    for f in MISSION.iterdir():
        if f.name.startswith("AOS_GS01"):
            return True
    return False

def run_sim():
    log_event("ORBIOS SIMULATOR ONLINE")
    
    while True:
        try:
            # 1. Update Physics
            sat_data = update_telemetry()
            
            # 2. Check current Downlink Status
            aos_active = is_aos_active()

            # 3. Handle Downlink Flushes (if AOS connects while items are in buffer)
            if aos_active:
                if STATE["onboard_anomaly"]:
                    fire_data = STATE["onboard_anomaly"]
                    log_event("DOWNLINK: ANOMALY FLUSHED TO GS-01", fire_data)
                    with open(MISSION / "HEAT_SPIKE_ACTIVE.json", "w") as jf:
                        json.dump(fire_data, jf)
                    STATE["onboard_anomaly"] = None

                if STATE["onboard_confirmed"]:
                    fire_data = STATE["onboard_confirmed"]
                    log_event("DOWNLINK: CONFIRMED ALERT FLUSHED TO GS-01", fire_data)
                    with open(MISSION / "FIRE_CONFIRMED.json", "w") as jf:
                        json.dump(fire_data, jf)
                    STATE["onboard_confirmed"] = None

            # 4. Check for incoming commands
            found_files = list(MISSION.iterdir())
            for f in found_files:
                fname = f.name
                
                if fname.startswith("INIT_FIRE"):
                    # Generate a fire near the satellite's path
                    fire_data = {
                        "type": "HEAT_ANOMALY",
                        "lat": sat_data["lat"] + random.uniform(-1.5, 1.5),
                        "lon": sat_data["lon"] + random.uniform(-1.5, 1.5),
                        "intensity": random.uniform(0.72, 0.96),
                        "status": "DETECTED"
                    }
                    
                    if aos_active:
                        log_event("DETECTION: DIRECT TELEMETRY DOWNLINKED", fire_data)
                        with open(MISSION / "HEAT_SPIKE_ACTIVE.json", "w") as jf:
                            json.dump(fire_data, jf)
                    else:
                        log_event("DETECTION: STORED ONBOARD (LINK OFFLINE)", fire_data)
                        STATE["onboard_anomaly"] = fire_data
                    f.unlink()

                elif fname.startswith("START_AI"):
                    # Check if we have any active raw fire (on disk or in buffer)
                    active_fire = None
                    if STATE["onboard_anomaly"]:
                        active_fire = STATE["onboard_anomaly"]
                    elif (MISSION / "HEAT_SPIKE_ACTIVE.json").exists():
                        try:
                            with open(MISSION / "HEAT_SPIKE_ACTIVE.json", "r") as rj:
                                active_fire = json.load(rj)
                        except Exception:
                            pass

                    if active_fire:
                        log_event("AI_AGENT: INITIATING EDGE INFERENCE")
                        time.sleep(2) # Simulated edge inference lag
                        
                        active_fire["status"] = "CONFIRMED"
                        
                        if aos_active:
                            log_event("AI_AGENT: WILDFIRE CONFIRMED - DOWNLINKED", active_fire)
                            with open(MISSION / "FIRE_CONFIRMED.json", "w") as jf:
                                json.dump(active_fire, jf)
                            
                            # Clean up unconfirmed raw maps markers
                            if (MISSION / "HEAT_SPIKE_ACTIVE.json").exists():
                                (MISSION / "HEAT_SPIKE_ACTIVE.json").unlink()
                        else:
                            log_event("AI_AGENT: WILDFIRE CONFIRMED - STORED", active_fire)
                            STATE["onboard_confirmed"] = active_fire
                            STATE["onboard_anomaly"] = None
                            
                            if (MISSION / "HEAT_SPIKE_ACTIVE.json").exists():
                                (MISSION / "HEAT_SPIKE_ACTIVE.json").unlink()
                    else:
                        log_event("AI_AGENT: ERROR - NO DETECTED ANOMALY FOUND")
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
