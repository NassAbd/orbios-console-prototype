#!/usr/bin/env python3
"""
Mac System Dashboard — Web Server (Satellite OBC Mock Integration)
──────────────────────────────────
Reads dashboard_config.yaml and serves live metrics as JSON.
Validated against schema.py Pydantic model SystemMetricsResponse.
"""

import argparse
import json
import platform
import socket
import sys
from datetime import datetime
from pathlib import Path

import psutil
import requests
import yaml
from flask import Flask, jsonify, send_from_directory
from schema import MissionAlert, OpenPBSJob, SystemMetricsResponse, WildfireAlertStatus

# Remote Pi configurations (will be overridden via CLI args)
PI_REMOTE_ENABLED = False
PI_IP = "192.168.2.2"
PI_PORT = 5006

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE        = Path(__file__).parent
CONFIG_PATH = BASE / "dashboard_config.yaml"
HTML_PATH   = BASE / "dashboard.html"
OUTPUT_DIR  = BASE.parent / "pi_part" / "algo_part" / "output"


app = Flask(__name__, static_folder=str(BASE))

# ── CORS ──────────────────────────────────────────────────────────────────────
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(str(BASE), "dashboard.html")

@app.route("/<path:path>")
def serve_static(path):
    if PI_REMOTE_ENABLED and (path.startswith("data/telemetry/") or path.startswith("signals/mission/")):
        try:
            url = f"http://{PI_IP}:{PI_PORT}/{path}"
            r = requests.get(url, timeout=3.0)
            if r.status_code == 200:
                if path.endswith(".json"):
                    return jsonify(r.json())
                return r.content, 200
            else:
                return f"Pi error: {r.status_code}", r.status_code
        except Exception as e:
            return f"Proxy error: {e}", 502
    return send_from_directory(str(BASE), path)

@app.route("/config")
def config_route():
    return jsonify(load_config())

def collect_local_metrics(phase: str) -> dict:
    # 1. CPU Metrics
    cpu_overall = psutil.cpu_percent(interval=None)
    cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
    if isinstance(cpu_per_core, float):
        cpu_per_core = [cpu_per_core]

    cpu_freq_obj = psutil.cpu_freq()
    frequency = int(cpu_freq_obj.current) if cpu_freq_obj else 1500
    freq_max = int(cpu_freq_obj.max) if cpu_freq_obj else 1500

    try:
        load_avg = list(psutil.getloadavg())
    except AttributeError:
        load_avg = [0.0, 0.0, 0.0]

    # 2. Memory Metrics
    vmem = psutil.virtual_memory()
    memory_pct = vmem.percent
    used_str = f"{(vmem.used / 1024**3):.1f} GB"
    total_str = f"{(vmem.total / 1024**3):.1f} GB"

    active_str = f"{(vmem.active / 1024**3):.1f} GB" if hasattr(vmem, "active") else None
    inactive_str = f"{(vmem.inactive / 1024**3):.1f} GB" if hasattr(vmem, "inactive") else None
    wired_str = f"{(vmem.buffers / 1024**3 + vmem.cached / 1024**3):.1f} GB" if hasattr(vmem, "buffers") else None

    swap = psutil.swap_memory()
    swap_pct = swap.percent
    swap_used_str = f"{(swap.used / 1024**2):.1f} MB"
    swap_total_str = f"{(swap.total / 1024**3):.1f} GB"

    # 3. Battery Metrics
    battery = {
        "available": False,
        "percent": None,
        "plugged": True,
        "secs_left": None,
        "cycle_count": None,
        "health": None
    }
    try:
        batt = psutil.sensors_battery()
        if batt:
            battery["available"] = True
            battery["percent"] = batt.percent
            battery["plugged"] = batt.power_plugged
            battery["secs_left"] = batt.secsleft if batt.secsleft != psutil.POWER_TIME_UNLIMITED else None
    except Exception:
        pass

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
        temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
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
        "sysinfo": sysinfo
    }


@app.route("/metrics")
def metrics():
    if PI_REMOTE_ENABLED:
        try:
            url = f"http://{PI_IP}:{PI_PORT}/api/metrics"
            r = requests.get(url, timeout=3.0)
            if r.status_code == 200:
                return jsonify(r.json())
            else:
                return jsonify({"error": f"Pi server status {r.status_code}"}), r.status_code
        except Exception as e:
            return jsonify({"error": f"Cannot reach Pi server: {e}"}), 502

    # 1. Determine C program execution phase based on created output files
    n_files = 0

    if OUTPUT_DIR.exists():
        n_files = len([f for f in OUTPUT_DIR.iterdir() if f.name.endswith(".dat")])

    # Phases mapping:
    # 0 files -> IDLE
    # 1-7 files -> PRE-PROCESSING
    # 8-13 files -> AI INFERENCE
    # 14-23 files -> POST-PROCESSING
    # 24+ files -> COMPLETED
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

    # 2. Collect real telemetry/metrics of local workstation
    local_metrics = collect_local_metrics(phase)

    # 3. Check for Active Alerts
    fire_confirmed_path = BASE.parent / "pi_part" / "signals" / "mission" / "FIRE_CONFIRMED.json"
    oil_leak_path = BASE.parent / "pi_part" / "signals" / "mission" / "OIL_LEAK_ACTIVE.json"

    active_alert = fire_confirmed_path.exists() or oil_leak_path.exists()
    alert_status = WildfireAlertStatus(active=active_alert)

    if fire_confirmed_path.exists():
        try:
            with open(fire_confirmed_path, "r") as f:
                alert_status.data = MissionAlert(**json.load(f))
        except Exception:
            pass
    elif oil_leak_path.exists():
        try:
            with open(oil_leak_path, "r") as f:
                alert_status.data = MissionAlert(**json.load(f))
        except Exception:
            pass

    # 4. OpenPBS Queue status
    pbs_queue_path = BASE.parent / "pi_part" / "signals" / "mission" / "pbs_queue.json"
    pbs_queue = []
    if pbs_queue_path.exists():
        try:
            with open(pbs_queue_path, "r") as f:
                pbs_queue = [OpenPBSJob(**job) for job in json.load(f)]
        except Exception:
            pass

    # Assemble response dictionary
    response_dict = {
        "cpu": local_metrics["cpu"],
        "memory": local_metrics["memory"],
        "battery": local_metrics["battery"],
        "disk": local_metrics["disk"],
        "temperature": local_metrics["temperature"],
        "processes": local_metrics["processes"],
        "users": local_metrics["users"],
        "sysinfo": local_metrics["sysinfo"],
        "wildfire_alert": alert_status.model_dump(),
        "pbs_queue": [j.model_dump() for j in pbs_queue]
    }

    # Validate against Schema before sending
    try:
        validated = SystemMetricsResponse.model_validate(response_dict)
        return jsonify(validated.model_dump())
    except Exception as e:
        print(f"[DASHBOARD] Schema validation failure: {e}", file=sys.stderr)
        return jsonify(response_dict)

def verify_pi_connection(ip: str, port: int):
    url = f"http://{ip}:{port}/api/metrics"
    print(f"[DASHBOARD] Validating connection to Raspberry Pi at {url}...")
    try:
        r = requests.get(url, timeout=3.0)
        if r.status_code == 200:
            print("[DASHBOARD] Successfully connected to Raspberry Pi.")
            return True
        else:
            print(f"[DASHBOARD] ERROR: Pi server returned status code {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"[DASHBOARD] ERROR: Cannot reach Raspberry Pi at {url}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", help="IP address of the remote Raspberry Pi")
    parser.add_argument("--port", type=int, default=5005, help="Port to run dashboard server locally")
    args = parser.parse_args()

    cfg  = load_config()
    host = cfg.get("server", {}).get("host", "127.0.0.1")
    port = args.port if args.port else cfg.get("server", {}).get("port", 5005)

    if args.remote:
        PI_REMOTE_ENABLED = True
        PI_IP = args.remote
        verify_pi_connection(PI_IP, PI_PORT)
        print(f"OrbiOS Workstation Dashboard running in REMOTE mode (Pi: {PI_IP}:{PI_PORT}) at http://{host}:{port}")
    else:
        print(f"OrbiOS Workstation Dashboard running in LOCAL mode at http://{host}:{port}")

    print(f"Config:                   {CONFIG_PATH}")
    print("Press Ctrl-C to stop.\n")

    app.run(host=host, port=port, debug=False)

