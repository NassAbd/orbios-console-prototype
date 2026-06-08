#!/usr/bin/env python3
import time
from typing import Any
import json
import pathlib
import subprocess
import re
from datetime import datetime
from skyfield.api import load, EarthSatellite
import platform
import socket
import threading
import psutil
from flask import Flask, jsonify, request, send_from_directory


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
LATCH_MSGS = {
    "BATT_HEATER_ON": ("THERMAL: BATTERY HEATER ACTIVATED", "THERMAL: BATTERY HEATER DEACTIVATED"),
    "BATT_HEATER_OFF": ("THERMAL: FORCE HEATER OFF ENABLED", "THERMAL: FORCE HEATER OFF DISABLED"),
    "STABILIZATION": ("AOCS: STABILIZATION CONTROL ACTIVE", "AOCS: STABILIZATION CONTROL INACTIVE"),
    "THERMAL_LOOP_MONITOR": ("THERMAL: LOOP MONITORING ONLINE", "THERMAL: LOOP MONITORING OFFLINE"),
    "ORBIT_RAISE_MANEUVER": ("PROPULSION: ORBIT MANEUVER MODE ACTIVE", "PROPULSION: ORBIT MANEUVER MODE INACTIVE"),
    "DETUMBLE_START": ("AOCS: DETUMBLE MODE ACTIVE", "AOCS: DETUMBLE MODE INACTIVE"),
    "NADIR_POINTING_ACQUISITION": ("AOCS: NADIR POINTING ACTIVE", "AOCS: NADIR POINTING INACTIVE"),
    "SOLAR_ARRAY_DEPLOY": ("POWER: SOLAR ARRAYS DEPLOYED", "POWER: SOLAR ARRAYS RETRACTED"),
    "CRYO_COOLER_START": ("THERMAL: CRYO COOLER ACTIVE", "THERMAL: CRYO COOLER INACTIVE"),
}

BUTTON_DAT_FILES = {
    "STAR_TRACKER_CALC": "Star_tracker_attitude_extraction.dat",
    "BATT_HEATER_OFF": "Battery_heater_off.dat",
    "BATT_HEATER_ON": "Battery_heater_on.dat",
    "STABILIZATION": "Stabilization.dat",
    "THERMAL_LOOP_MONITOR": "Thermal_loop_monitor.dat",
    "ORBIT_RAISE_MANEUVER": "Orbit_raise_maneuver.dat",
    "THRUSTER_PURGE": "Thruster_purge.dat",
    "DETUMBLE_START": "Detumble_start.dat",
    "NADIR_POINTING_ACQUISITION": "Nadir_pointing_acquisition.dat",
    "SOLAR_ARRAY_DEPLOY": "Solar_array_deploy.dat",
    "CRYO_COOLER_START": "Cryo_cooler_start.dat",
}

def touch_output_file(name):
    target = OUTPUT_DIR / name
    try:
        target.touch()
        print(f"[SIM] Touched output file: {target}")
    except Exception as e:
        print(f"[SIM] Error touching output file {target}: {e}")

def remove_output_file(name):
    target = OUTPUT_DIR / name
    if target.exists():
        try:
            target.unlink()
            print(f"[SIM] Removed output file: {target}")
        except Exception as e:
            print(f"[SIM] Error removing output file {target}: {e}")
    if name in STATE["processed_output_files"]:
        STATE["processed_output_files"].remove(name)


STATE: dict[str, Any] = {
    "algo_process": None,
    "onboard_confirmed_wildfires": [],
    "onboard_confirmed_oilleaks": [],
    "processed_output_files": set(),
    "false_alert_clear_time": None,
    "completed_display_ticks": 0,
    "active_alerts": [],
    "latched_states": {k: False for k in LATCH_MSGS}
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
    STATE["latched_states"] = {k: False for k in LATCH_MSGS}
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

            # 6b. Process latched state files from UI buttons
            if MISSION.exists():
                current_files = [f.name for f in list(MISSION.iterdir())]
                for state_name, (on_msg, off_msg) in LATCH_MSGS.items():
                    is_active = any(name.startswith(state_name) for name in current_files)
                    was_active = STATE["latched_states"].get(state_name, False)
                    dat_file = BUTTON_DAT_FILES.get(state_name)
                    if is_active and not was_active:
                        STATE["latched_states"][state_name] = True
                        if dat_file:
                            touch_output_file(dat_file)
                        else:
                            log_event(on_msg)
                    elif not is_active and was_active:
                        STATE["latched_states"][state_name] = False
                        if dat_file:
                            remove_output_file(dat_file)
                        log_event(off_msg)

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
                            
                    elif fname.startswith("STAR_TRACKER_CALC"):
                        dat_file = BUTTON_DAT_FILES.get("STAR_TRACKER_CALC")
                        if dat_file:
                            touch_output_file(dat_file)
                        try:
                            f.unlink()
                        except Exception:
                            pass
                            
                    elif fname.startswith("THRUSTER_PURGE"):
                        dat_file = BUTTON_DAT_FILES.get("THRUSTER_PURGE")
                        if dat_file:
                            touch_output_file(dat_file)
                        try:
                            f.unlink()
                        except Exception:
                            pass

            time.sleep(0.5)
        except Exception as e:
            print(f"Sim Error: {e}")
            time.sleep(1)

def collect_pi_metrics() -> dict:
    # 1. CPU Metrics
    cpu_overall = psutil.cpu_percent(interval=None)
    cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
    if isinstance(cpu_per_core, float):
        cpu_per_core = [cpu_per_core]
    
    # cpu freq
    cpu_freq_obj = psutil.cpu_freq()
    frequency = int(cpu_freq_obj.current) if cpu_freq_obj else 1500
    freq_max = int(cpu_freq_obj.max) if cpu_freq_obj else 1500
    
    # load average
    try:
        load_avg = list(psutil.getloadavg())
    except AttributeError:
        load_avg = [0.0, 0.0, 0.0]
        
    # 2. Memory Metrics
    vmem = psutil.virtual_memory()
    memory_pct = vmem.percent
    used_str = f"{(vmem.used / 1024**3):.1f} GB"
    total_str = f"{(vmem.total / 1024**3):.1f} GB"
    
    # Linux-specific active/inactive/buffers/cached
    active_str = f"{(vmem.active / 1024**3):.1f} GB" if hasattr(vmem, "active") else None
    inactive_str = f"{(vmem.inactive / 1024**3):.1f} GB" if hasattr(vmem, "inactive") else None
    wired_str = f"{(vmem.buffers / 1024**3 + vmem.cached / 1024**3):.1f} GB" if hasattr(vmem, "buffers") else None
    
    # swap
    swap = psutil.swap_memory()
    swap_pct = swap.percent
    swap_used_str = f"{(swap.used / 1024**2):.1f} MB"
    swap_total_str = f"{(swap.total / 1024**3):.1f} GB"
    
    # 3. Battery Metrics - adapted for Pi (which is wall powered)
    battery = {
        "available": False,
        "percent": None,
        "plugged": True,
        "secs_left": None,
        "cycle_count": None,
        "health": None
    }
    
    # 4. Disk Metrics
    usage = psutil.disk_usage('/')
    partitions = [{
        "mount": "/",
        "percent": usage.percent,
        "used_str": f"{(usage.used / 1024**3):.1f} GB",
        "total_str": f"{(usage.total / 1024**3):.1f} GB"
    }]
    
    read_rate = "0.0 B/s"
    write_rate = "0.0 B/s"
    
    # 5. Temperature Metrics
    temp_val = None
    try:
        temp_path = pathlib.Path("/sys/class/thermal/thermal_zone0/temp")
        if temp_path.exists():
            temp_val = float(temp_path.read_text().strip()) / 1000.0
    except Exception:
        pass
        
    if temp_val is None:
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for k, v in temps.items():
                    if v:
                        temp_val = v[0].current
                        break
        except Exception:
            pass
    if temp_val is None:
        temp_val = 45.0
        
    # 6. Process listing
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
        try:
            info = proc.info
            processes.append({
                "pid": info["pid"],
                "name": info["name"] or "unknown",
                "user": info["username"] or "unknown",
                "cpu": info["cpu_percent"] or 0.0,
                "mem": info["memory_percent"] or 0.0
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    processes = sorted(processes, key=lambda p: (p["cpu"], p["mem"]), reverse=True)[:10]
    
    # 7. Users
    users = []
    try:
        for u in psutil.users():
            try:
                since_str = datetime.fromtimestamp(u.started).strftime("%b %d %H:%M")
            except Exception:
                since_str = "unknown"
            users.append({
                "name": u.name,
                "terminal": u.terminal or "ssh",
                "since": since_str
            })
    except Exception:
        pass
        
    # 8. Sysinfo (with phase mapping for uptime)
    n_files = 0
    if OUTPUT_DIR.exists():
        n_files = len([f for f in OUTPUT_DIR.iterdir() if f.name.endswith(".dat")])
    if n_files == 0:
        phase = "IDLE"
    elif n_files <= 7:
        phase = "PRE-PROCESSING"
    elif n_files <= 13:
        phase = "AI INFERENCE"
    elif n_files < 24:
        phase = "POST-PROCESSING"
    else:
        phase = "COMPLETED"
        
    try:
        boot_time_str = datetime.fromtimestamp(psutil.boot_time()).strftime("%d %b %Y %H:%M")
    except Exception:
        boot_time_str = "unknown"
        
    sysinfo = {
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "arch": platform.machine(),
        "boot_time": boot_time_str,
        "uptime": phase,
        "cpu_count": psutil.cpu_count() or 4
    }
    
    return {
        "cpu": {
            "overall": cpu_overall,
            "per_core": cpu_per_core,
            "frequency": frequency,
            "freq_max": freq_max,
            "load_avg": load_avg
        },
        "memory": {
            "percent": memory_pct,
            "used_str": used_str,
            "total_str": total_str,
            "active": active_str,
            "inactive": inactive_str,
            "wired": wired_str,
            "swap_percent": swap_pct,
            "swap_used_str": swap_used_str,
            "swap_total_str": swap_total_str
        },
        "battery": battery,
        "disk": {
            "partitions": partitions,
            "read_rate": read_rate,
            "write_rate": write_rate
        },
        "temperature": {
            "value": temp_val
        },
        "processes": processes,
        "users": users,
        "sysinfo": sysinfo,
        "wildfire_alert": {"active": False},
        "pbs_queue": []
    }

# --- Pi HTTP API Server ---
pi_app = Flask("orbios_pi_server")

@pi_app.route("/api/metrics")
def pi_metrics():
    metrics_dict = collect_pi_metrics()
    
    # Check for active mission alerts
    fire_confirmed_path = MISSION / "FIRE_CONFIRMED.json"
    oil_leak_path = MISSION / "OIL_LEAK_ACTIVE.json"
    active_alert = fire_confirmed_path.exists() or oil_leak_path.exists()
    
    metrics_dict["wildfire_alert"]["active"] = active_alert
    
    if fire_confirmed_path.exists():
        try:
            with open(fire_confirmed_path, "r") as f:
                metrics_dict["wildfire_alert"]["data"] = json.load(f)
        except Exception:
            pass
    elif oil_leak_path.exists():
        try:
            with open(oil_leak_path, "r") as f:
                metrics_dict["wildfire_alert"]["data"] = json.load(f)
        except Exception:
            pass
            
    # Check PBS queue
    pbs_queue_path = MISSION / "pbs_queue.json"
    if pbs_queue_path.exists():
        try:
            with open(pbs_queue_path, "r") as f:
                metrics_dict["pbs_queue"] = json.load(f)
        except Exception:
            pass
            
    return jsonify(metrics_dict)

@pi_app.route("/api/touch", methods=["POST"])
def pi_touch():
    data = request.json or {}
    dir_name = data.get("dir", "")
    name = data.get("name", "")
    if not dir_name or not name:
        return jsonify({"ok": False, "error": "dir and name required"}), 400
    try:
        target = (PROJECT_ROOT / dir_name / name).resolve()
        if not str(target).startswith(str(PROJECT_ROOT)):
            return jsonify({"ok": False, "error": "Access denied"}), 403
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
        print(f"[PI_API] TOUCH {target}")
        return jsonify({"ok": True, "path": str(target)})
    except Exception as e:
        print(f"[PI_API] TOUCH ERROR: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@pi_app.route("/api/remove", methods=["POST"])
def pi_remove():
    data = request.json or {}
    dir_name = data.get("dir", "")
    name = data.get("name", "")
    if not dir_name or not name:
        return jsonify({"ok": False, "error": "dir and name required"}), 400
    try:
        target = (PROJECT_ROOT / dir_name / name).resolve()
        if not str(target).startswith(str(PROJECT_ROOT)):
            return jsonify({"ok": False, "error": "Access denied"}), 403
        if target.exists():
            target.unlink()
            print(f"[PI_API] REMOVE {target}")
        return jsonify({"ok": True})
    except Exception as e:
        print(f"[PI_API] REMOVE ERROR: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@pi_app.route("/api/listdir", methods=["POST"])
def pi_listdir():
    data = request.json or {}
    dir_name = data.get("dir", "")
    if not dir_name:
        return jsonify({"files": [], "error": "dir required"}), 400
    try:
        p = (PROJECT_ROOT / dir_name).resolve()
        if not str(p).startswith(str(PROJECT_ROOT)):
            return jsonify({"files": [], "error": "Access denied"}), 403
        if not p.is_dir():
            return jsonify({"files": []})
        sorted_files = sorted([f for f in p.iterdir() if f.is_file()], key=lambda f: f.stat().st_mtime)
        return jsonify({"files": [f.name for f in sorted_files]})
    except Exception as e:
        print(f"[PI_API] LISTDIR ERROR: {e}")
        return jsonify({"files": [], "error": str(e)}), 500

@pi_app.route("/data/telemetry/sat_01.json")
def pi_telemetry():
    return send_from_directory(str(PROJECT_ROOT / "data" / "telemetry"), "sat_01.json")

@pi_app.route("/signals/mission/<filename>")
def pi_mission_signal(filename):
    filename = pathlib.Path(filename).name
    return send_from_directory(str(PROJECT_ROOT / "signals" / "mission"), filename)

def start_pi_api_server():
    print("[PI_SERVER] Starting API server on port 5006...")
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    pi_app.run(host="0.0.0.0", port=5006, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Start the API server thread
    api_thread = threading.Thread(target=start_pi_api_server, daemon=True)
    api_thread.start()
    
    try:
        run_sim()
    except KeyboardInterrupt:
        log_event("SIMULATOR STOPPED")
        if STATE["algo_process"]:
            try:
                STATE["algo_process"].kill()
            except Exception:
                pass

