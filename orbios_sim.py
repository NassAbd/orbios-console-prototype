#!/usr/bin/env python3
import time
from typing import Any
import json
import pathlib
import subprocess
import re
from datetime import datetime
from skyfield.api import load, EarthSatellite

# --- Paths ---
PROJECT_ROOT = pathlib.Path(__file__).parent.absolute()
SIGNALS      = PROJECT_ROOT / "signals"
DATA         = PROJECT_ROOT / "data"
MISSION      = SIGNALS / "mission"
LOGS         = SIGNALS / "logs"
ALGO_DIR     = PROJECT_ROOT / "algo_part"
OUTPUT_DIR   = ALGO_DIR / "output"

# Ensure directories exist
for p in [MISSION, LOGS, DATA / "telemetry", OUTPUT_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# --- State Management ---
STATE: dict[str, Any] = {
    "algo_process": None,
    "onboard_confirmed_wildfires": [],
    "onboard_confirmed_oilleaks": [],
    "processed_output_files": set(),
    "false_alert_clear_time": None,
    "completed_display_ticks": 0,
    "active_alerts": []
}

# --- Orbital Setup ---
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
    telemetry = {
        "id": "ORBIOS-S1",
        "lat": 40.2000,
        "lon": -7.8000,
        "alt_km": 420.0,
        "timestamp": datetime.now().isoformat()
    }
    
    with open(DATA / "telemetry" / "sat_01.json", "w") as f:
        json.dump(telemetry, f)
    return telemetry

def clean_signals():
    print("[SIM] Cleaning signals and output folders...")
    for f in MISSION.iterdir():
        try:
            f.unlink()
        except Exception:
            pass
    for f in LOGS.iterdir():
        try:
            f.unlink()
        except Exception:
            pass
    if OUTPUT_DIR.exists():
        for f in OUTPUT_DIR.iterdir():
            if f.name.endswith(".dat") or f.name.endswith(".json"):
                try:
                    f.unlink()
                except Exception:
                    pass
    STATE["onboard_confirmed_wildfires"] = []
    STATE["onboard_confirmed_oilleaks"] = []
    STATE["processed_output_files"] = set()
    STATE["false_alert_clear_time"] = None
    STATE["completed_display_ticks"] = 0
    STATE["active_alerts"] = []
    if STATE["algo_process"]:
        try:
            STATE["algo_process"].terminate()
            STATE["algo_process"].wait()
        except Exception:
            pass
        STATE["algo_process"] = None

def check_and_clear_expired_alerts():
    now = time.time()
    remaining = []
    for alert in STATE.get("active_alerts", []):
        if now >= alert["expires_at"]:
            path = pathlib.Path(alert["path"])
            if path.exists():
                try:
                    path.unlink()
                except Exception as e:
                    print(f"Error deleting expired alert {path}: {e}")
            log_event(f"AI_AGENT: VISUAL ALERT EXPIRED - REMOVING {path.name}")
        else:
            remaining.append(alert)
    STATE["active_alerts"] = remaining

def is_aos_active():
    """Always return True to downlink data directly to the ground station"""
    return True

def compile_algo():
    print("[SIM] Compiling C algo code...")
    try:
        subprocess.run(["gcc", "-o", "main2", "main2.c", "payload.c"], cwd=ALGO_DIR, check=True)
        print("[SIM] Compilation successful.")
    except Exception as e:
        print(f"[SIM] Error compiling C code: {e}")

def parse_lat_lon_type(filename):
    clean_name = filename.replace(".dat", "")
    lat_match = re.search(r"LAT(-?[\d.]+)", clean_name)
    lon_match = re.search(r"LON(-?[\d.]+)", clean_name)
    if not lat_match or not lon_match:
        return None
    lat = float(lat_match.group(1))
    lon = float(lon_match.group(1))
    
    if "WILDFIRE" in filename:
        return lat, lon, "WILDFIRE"
    elif "FALSE_ALERT" in filename:
        return lat, lon, "FALSE_ALERT"
    elif "OIL_LEAK" in filename:
        return lat, lon, "OIL_LEAK"
    return None

def handle_new_output_file(filename):
    name_no_ext = filename
    if filename.endswith(".dat"):
        name_no_ext = filename[:-4]
    
    # Write chronological log for Control Panel UI terminal
    log_event(name_no_ext.replace('_', ' '))
    
    # Parse coordinates and alert type
    parsed = parse_lat_lon_type(filename)
    if not parsed:
        return
        
    lat, lon, alert_type = parsed
    
    if alert_type == "WILDFIRE":
        alert = {
            "type": "WILDFIRE",
            "lat": lat,
            "lon": lon,
            "intensity": 0.85,
            "status": "CONFIRMED",
            "alert_msg": f"CRITICAL WILDFIRE LAT {lat:.4f} LON {lon:.4f}"
        }
        if is_aos_active():
            log_event("COMMS: SENDING WILDFIRE ALERT TO GS-01", alert)
            dest_path = MISSION / "FIRE_CONFIRMED.json"
            with open(dest_path, "w") as jf:
                json.dump(alert, jf)
            STATE.setdefault("active_alerts", []).append({
                "path": str(dest_path),
                "expires_at": time.time() + 3.0
            })
        else:
            log_event("COMMS: LINK OFFLINE - BUFFERING WILDFIRE ALERT", alert)
            STATE["onboard_confirmed_wildfires"].append(alert)
            
    elif alert_type == "FALSE_ALERT":
        alert = {
            "type": "HEAT_ANOMALY",
            "lat": lat,
            "lon": lon,
            "intensity": 0.35,
            "status": "DETECTED"
        }
        log_event("DETECTION: FALSE ALARM TELEMETRY DOWNLINKED", alert)
        with open(MISSION / "HEAT_SPIKE_ACTIVE.json", "w") as jf:
            json.dump(alert, jf)
        STATE["false_alert_clear_time"] = time.time() + 3.0
        
    elif alert_type == "OIL_LEAK":
        alert = {
            "type": "OIL_LEAK",
            "lat": lat,
            "lon": lon,
            "intensity": 0.90,
            "status": "CONFIRMED",
            "alert_msg": f"CRITICAL OIL LEAK LAT {lat:.4f} LON {lon:.4f}"
        }
        if is_aos_active():
            log_event("COMMS: SENDING OIL LEAK ALERT TO GS-01", alert)
            dest_path = MISSION / "OIL_LEAK_ACTIVE.json"
            with open(dest_path, "w") as jf:
                json.dump(alert, jf)
            STATE.setdefault("active_alerts", []).append({
                "path": str(dest_path),
                "expires_at": time.time() + 3.0
            })
        else:
            log_event("COMMS: LINK OFFLINE - BUFFERING OIL LEAK ALERT", alert)
            STATE["onboard_confirmed_oilleaks"].append(alert)

def run_sim():
    log_event("ORBIOS SIMULATOR ONLINE")
    compile_algo()
    
    # Clean start
    clean_signals()
    
    while True:
        try:
            # 1. Update Physics
            update_telemetry()
            
            # 2. Check current Downlink Status
            aos_active = is_aos_active()

            # 3. Handle Downlink Flushes
            if aos_active:
                if STATE["onboard_confirmed_wildfires"]:
                    for alert in STATE["onboard_confirmed_wildfires"]:
                        log_event("DOWNLINK: CONFIRMED WILDFIRE FLUSHED TO GS-01", alert)
                        dest_path = MISSION / "FIRE_CONFIRMED.json"
                        with open(dest_path, "w") as jf:
                            json.dump(alert, jf)
                        STATE.setdefault("active_alerts", []).append({
                            "path": str(dest_path),
                            "expires_at": time.time() + 3.0
                        })
                    STATE["onboard_confirmed_wildfires"] = []
                if STATE["onboard_confirmed_oilleaks"]:
                    for alert in STATE["onboard_confirmed_oilleaks"]:
                        log_event("DOWNLINK: OIL LEAK FLUSHED TO GS-01", alert)
                        dest_path = MISSION / "OIL_LEAK_ACTIVE.json"
                        with open(dest_path, "w") as jf:
                            json.dump(alert, jf)
                        STATE.setdefault("active_alerts", []).append({
                            "path": str(dest_path),
                            "expires_at": time.time() + 3.0
                        })
                    STATE["onboard_confirmed_oilleaks"] = []

            # 4. Handle False Alert removal timing
            if STATE["false_alert_clear_time"] and time.time() >= STATE["false_alert_clear_time"]:
                spike_path = MISSION / "HEAT_SPIKE_ACTIVE.json"
                if spike_path.exists():
                    spike_path.unlink()
                STATE["false_alert_clear_time"] = None
                log_event("AI_AGENT: SIGNAL IS INVALID - IGNORING")

            # 4b. Handle expired active visual alerts (e.g. fire/oil)
            check_and_clear_expired_alerts()

            # 5. Monitor C program output folder
            if OUTPUT_DIR.exists():
                found_files = [f.name for f in OUTPUT_DIR.iterdir() if f.name.endswith(".dat")]
                # Sort alphabetically to avoid directory listing order discrepancies, 
                # but process them dynamically as they appear.
                for fname in sorted(found_files):
                    if fname not in STATE["processed_output_files"]:
                        STATE["processed_output_files"].add(fname)
                        handle_new_output_file(fname)

            # 6. Update OpenPBS queue status file based on C program process
            proc = STATE["algo_process"]
            if proc:
                # Check running status
                is_running = proc.poll() is None
                n_files = len([f for f in OUTPUT_DIR.iterdir() if f.name.endswith(".dat")])
                progress = int((n_files / 24) * 100)
                if progress > 100:
                    progress = 100
                
                if is_running:
                    job = {
                        "job_id": "PBS-1024",
                        "task": "WILDFIRE_EDGE_INFERENCE",
                        "status": "RUNNING",
                        "node": "WORKSTATION-01 (via SSH)",
                        "progress": progress,
                        "ticks": 0
                    }
                    with open(MISSION / "pbs_queue.json", "w") as f:
                        json.dump([job], f)
                else:
                    # Just finished
                    if progress == 100 and proc.returncode == 0:
                        job = {
                            "job_id": "PBS-1024",
                            "task": "WILDFIRE_EDGE_INFERENCE",
                            "status": "COMPLETED",
                            "node": "WORKSTATION-01 (via SSH)",
                            "progress": 100,
                            "ticks": STATE["completed_display_ticks"]
                        }
                        with open(MISSION / "pbs_queue.json", "w") as f:
                            json.dump([job], f)
                        STATE["completed_display_ticks"] += 1
                        if STATE["completed_display_ticks"] >= 6: # Display completed for 3 seconds
                            STATE["algo_process"] = None
                            if (MISSION / "pbs_queue.json").exists():
                                (MISSION / "pbs_queue.json").unlink()
                    else:
                        # Process terminated unexpectedly or was killed
                        STATE["algo_process"] = None
                        if (MISSION / "pbs_queue.json").exists():
                            (MISSION / "pbs_queue.json").unlink()

            # 7. Check for incoming commands from UI buttons
            if MISSION.exists():
                for f in list(MISSION.iterdir()):
                    fname = f.name
                    
                    if fname.startswith("START_AI"):
                        if not STATE["algo_process"]:
                            log_event("PBS: SUBMITTING JOB PBS-1024 TO TASK SCHEDULER")
                            # Clear old output files before running C algo
                            for out_file in OUTPUT_DIR.iterdir():
                                if out_file.name.endswith(".dat"):
                                    try:
                                        out_file.unlink()
                                    except Exception:
                                        pass
                            STATE["processed_output_files"] = set()
                            STATE["completed_display_ticks"] = 0
                            
                            # Queue initial state
                            job = {
                                "job_id": "PBS-1024",
                                "task": "WILDFIRE_EDGE_INFERENCE",
                                "status": "QUEUED",
                                "node": "WORKSTATION-01 (via SSH)",
                                "progress": 0,
                                "ticks": 0
                            }
                            with open(MISSION / "pbs_queue.json", "w") as jf:
                                json.dump([job], jf)
                                
                            # Spawn the C program
                            try:
                                STATE["algo_process"] = subprocess.Popen(
                                    ["./main2"],
                                    cwd=ALGO_DIR,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True
                                )
                                log_event("PBS: JOB PBS-1024 DISPATCHED TO WORKSTATION-01 via SSH")
                            except Exception as e:
                                log_event(f"ERROR launching C algo process: {e}")
                                STATE["algo_process"] = None
                        try:
                            f.unlink()
                        except Exception:
                            pass
                        
                    elif fname.startswith("RESET"):
                        log_event("SYSTEM RESET COMMAND RECEIVED")
                        clean_signals()
                        log_event("ORBIOS SIMULATOR ONLINE")
                        try:
                            f.unlink()
                        except Exception:
                            pass
                        
                    elif fname.startswith("INIT_FIRE"):
                        log_event("DETECTION: RAW SIGNAL ACQUIRED FROM PORTUGAL SECTOR")
                        try:
                            f.unlink()
                        except Exception:
                            pass
                        
                    elif fname.startswith("INIT_FALSE"):
                        log_event("DETECTION: FALSE ALARM TELEMETRY DOWNLINKED")
                        try:
                            f.unlink()
                        except Exception:
                            pass

            time.sleep(0.5)
        except Exception as e:
            print(f"Sim Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    try:
        run_sim()
    except KeyboardInterrupt:
        log_event("SIMULATOR STOPPED")
        if STATE["algo_process"]:
            try:
                STATE["algo_process"].kill()
            except Exception:
                pass
