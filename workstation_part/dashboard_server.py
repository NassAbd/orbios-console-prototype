#!/usr/bin/env python3
"""
Mac System Dashboard — Web Server (Satellite OBC Mock Integration)
──────────────────────────────────
Reads dashboard_config.yaml and serves live metrics as JSON.
Validated against schema.py Pydantic model SystemMetricsResponse.
"""

import sys
import json
import yaml
import argparse
import requests
from pathlib import Path
from flask import Flask, jsonify, send_from_directory

from schema import (
    SystemMetricsResponse,
    CpuMetrics,
    MemoryMetrics,
    BatteryMetrics,
    DiskMetrics,
    DiskPartition,
    TemperatureMetrics,
    ProcessInfo,
    UserInfo,
    SysInfoMetrics,
    WildfireAlertStatus,
    MissionAlert,
    OpenPBSJob
)

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

    # 2. Build mock telemetry/metrics representing the Satellite OBC
    # CPU Metrics
    if phase == "IDLE":
        cpu = CpuMetrics(overall=4.2, per_core=[3.1, 5.0, 2.8, 5.9], frequency=1200, freq_max=3200, load_avg=[0.05, 0.08, 0.12])
    elif phase == "PRE-PROCESSING":
        cpu = CpuMetrics(overall=38.5, per_core=[35.2, 42.1, 37.8, 39.0], frequency=2400, freq_max=3200, load_avg=[0.45, 0.38, 0.28])
    elif phase == "AI INFERENCE":
        cpu = CpuMetrics(overall=95.8, per_core=[96.5, 94.2, 98.1, 94.4], frequency=3200, freq_max=3200, load_avg=[2.85, 1.95, 1.25])
    elif phase == "POST-PROCESSING":
        cpu = CpuMetrics(overall=48.2, per_core=[46.1, 52.3, 44.8, 49.5], frequency=2400, freq_max=3200, load_avg=[0.65, 0.58, 0.48])
    else: # COMPLETED
        cpu = CpuMetrics(overall=4.5, per_core=[3.8, 5.1, 3.4, 5.5], frequency=1200, freq_max=3200, load_avg=[0.08, 0.12, 0.18])

    # Memory Metrics
    if phase == "IDLE":
        memory = MemoryMetrics(percent=24.5, used_str="3.9 GB", total_str="16.0 GB", active="1.2 GB", inactive="2.0 GB", wired="0.7 GB", swap_percent=5.0, swap_used_str="204.8 MB", swap_total_str="4.0 GB")
    elif phase == "PRE-PROCESSING":
        memory = MemoryMetrics(percent=45.2, used_str="7.2 GB", total_str="16.0 GB", active="3.5 GB", inactive="2.5 GB", wired="1.2 GB", swap_percent=8.5, swap_used_str="348.2 MB", swap_total_str="4.0 GB")
    elif phase == "AI INFERENCE":
        memory = MemoryMetrics(percent=82.7, used_str="13.2 GB", total_str="16.0 GB", active="8.5 GB", inactive="3.1 GB", wired="1.6 GB", swap_percent=42.1, swap_used_str="1.7 GB", swap_total_str="4.0 GB")
    elif phase == "POST-PROCESSING":
        memory = MemoryMetrics(percent=54.8, used_str="8.8 GB", total_str="16.0 GB", active="5.1 GB", inactive="2.3 GB", wired="1.4 GB", swap_percent=12.5, swap_used_str="512.0 MB", swap_total_str="4.0 GB")
    else: # COMPLETED
        memory = MemoryMetrics(percent=25.1, used_str="4.0 GB", total_str="16.0 GB", active="1.3 GB", inactive="2.0 GB", wired="0.7 GB", swap_percent=5.2, swap_used_str="213.0 MB", swap_total_str="4.0 GB")

    # Battery (Satellite solar/onboard power reserve)
    if phase == "IDLE":
        battery = BatteryMetrics(available=True, percent=98.0, plugged=True, secs_left=None, cycle_count="342", health="Normal")
    elif phase == "PRE-PROCESSING":
        battery = BatteryMetrics(available=True, percent=85.0, plugged=False, secs_left=3600, cycle_count="342", health="Normal")
    elif phase == "AI INFERENCE":
        battery = BatteryMetrics(available=True, percent=68.0, plugged=False, secs_left=1200, cycle_count="342", health="Normal")
    elif phase == "POST-PROCESSING":
        battery = BatteryMetrics(available=True, percent=52.0, plugged=False, secs_left=2400, cycle_count="342", health="Normal")
    else: # COMPLETED
        battery = BatteryMetrics(available=True, percent=48.0, plugged=True, secs_left=None, cycle_count="342", health="Normal")

    # Disk partition (OBC raw storage)
    read_rate = "0.0 B/s" if phase in ("IDLE", "COMPLETED") else "12.4 MB/s"
    write_rate = "0.0 B/s" if phase in ("IDLE", "COMPLETED") else "18.2 MB/s"
    disk = DiskMetrics(
        partitions=[DiskPartition(mount="/", percent=14.5, used_str="18.2 GB", total_str="128.0 GB")],
        read_rate=read_rate,
        write_rate=write_rate
    )

    # Temperature (OBC sensor core temp)
    if phase == "IDLE":
        temp_val = 38.5
    elif phase == "PRE-PROCESSING":
        temp_val = 52.4
    elif phase == "AI INFERENCE":
        temp_val = 84.8
    elif phase == "POST-PROCESSING":
        temp_val = 61.2
    else: # COMPLETED
        temp_val = 42.1
    temperature = TemperatureMetrics(value=temp_val)

    # Mock satellite OS processes listing
    processes = []
    if phase != "IDLE":
        processes.append(ProcessInfo(pid=1024, name="main2", user="root", cpu=95.0 if phase == "AI INFERENCE" else 40.0, mem=22.4 if phase == "AI INFERENCE" else 5.2))
        processes.append(ProcessInfo(pid=1025, name="aocs_control", user="root", cpu=22.0 if phase == "POST-PROCESSING" else 2.5, mem=4.2))
        processes.append(ProcessInfo(pid=1026, name="thermal_mgmt", user="root", cpu=8.5 if phase == "AI INFERENCE" else 1.2, mem=1.1))
        processes.append(ProcessInfo(pid=1027, name="telemetry_tx", user="root", cpu=12.0 if phase == "PRE-PROCESSING" else 1.0, mem=2.3))
    processes.append(ProcessInfo(pid=1, name="obc_kernel", user="root", cpu=2.1, mem=1.2))
    processes.append(ProcessInfo(pid=22, name="payload_mgr", user="root", cpu=4.8, mem=3.5))

    # Logged-in Users
    users = [
        UserInfo(name="root", terminal="console", since="May 28 08:00"),
        UserInfo(name="ai_agent", terminal="ssh", since="May 28 14:30")
    ]

    # Uptime & SysInfo metrics
    # Hostname: OBC system ID, Uptime: OBC pipeline active phase string
    sysinfo = SysInfoMetrics(
        hostname="ORBIOS-OBC-S1",
        os="Ubuntu Linux 24.04 (RT-Kernel)",
        arch="aarch64",
        boot_time="28 May 2026 08:00",
        uptime=phase,
        cpu_count=4
    )

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
        "cpu": cpu.model_dump(),
        "memory": memory.model_dump(),
        "battery": battery.model_dump(),
        "disk": disk.model_dump(),
        "temperature": temperature.model_dump(),
        "processes": [p.model_dump() for p in processes],
        "users": [u.model_dump() for u in users],
        "sysinfo": sysinfo.model_dump(),
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

