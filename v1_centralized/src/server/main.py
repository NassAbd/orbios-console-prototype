#!/usr/bin/env python3
import os
import json
import time
import random
import threading
import psutil
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, jsonify, send_from_directory, request
from src.server.schema import (
    GlobalState, Satellite, FireZone, Telemetry, 
    MissionTask, SatelliteStatus, TaskStage, CommMessage
)
from src.server.satellite_engine import SatelliteEngine

# --- Paths ---
BASE = Path(__file__).parent.parent.parent
CONFIG_DIR = BASE / "config"
WEB_DIR = BASE / "src" / "web"
SATELLITE_CONFIG = CONFIG_DIR / "satellite_config.json"

app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path='')

# --- State ---
fire_zones = []
task_queue = []
messages = []
satellite_dynamic_states = {} # nid -> {status, current_task_id}

sat_engine = SatelliteEngine(SATELLITE_CONFIG)

def add_message(origin, payload, level="INFO"):
    messages.append(CommMessage(
        timestamp=datetime.now(),
        origin=origin,
        payload=payload,
        level=level
    ))
    if len(messages) > 50: messages.pop(0)

# --- PBS Simulation Engine ---
def simulation_loop():
    while True:
        try:
            for task in task_queue:
                if task.status == "COMPLETED": continue
                
                # PBS Scheduler Logic: Q -> R
                if task.status == "QUEUED":
                    task.status = "RUNNING"
                    if task.assigned_satellite_id:
                        satellite_dynamic_states[task.assigned_satellite_id] = {"status": SatelliteStatus.IDLE, "current_task_id": task.task_id}
                    add_message("GS", f"Job {task.task_id} allocated to node SAT-{task.assigned_satellite_id}", "INFO")
                    continue

                # Progress through stages
                task.progress += 2.0
                
                if task.progress >= 100.0:
                    task.status = "COMPLETED"
                    task.stage = TaskStage.COMPLETED
                    if task.assigned_satellite_id:
                        satellite_dynamic_states[task.assigned_satellite_id] = {"status": SatelliteStatus.IDLE, "current_task_id": None}
                    add_message("GS", f"Job {task.task_id} completed successfully.", "INFO")
                    continue

                # Stage updates
                if task.progress < 25:
                    task.stage = TaskStage.HEAT_DETECTION
                elif task.progress < 50:
                    if task.stage != TaskStage.IMAGING_ACQUISITION:
                        task.stage = TaskStage.IMAGING_ACQUISITION
                        if task.assigned_satellite_id:
                            satellite_dynamic_states[task.assigned_satellite_id]["status"] = SatelliteStatus.IMAGING
                        add_message("SAT", f"Payload active: imaging {task.task_id}", "INFO")
                elif task.progress < 75:
                    if task.stage != TaskStage.AI_INFERENCE:
                        task.stage = TaskStage.AI_INFERENCE
                        if task.assigned_satellite_id:
                            satellite_dynamic_states[task.assigned_satellite_id]["status"] = SatelliteStatus.AI_PROCESSING
                        add_message("AI", f"Inference engine processing job {task.task_id}", "WARN")
                else:
                    if task.stage != TaskStage.GS_REPORTING:
                        task.stage = TaskStage.GS_REPORTING
                        if task.assigned_satellite_id:
                            satellite_dynamic_states[task.assigned_satellite_id]["status"] = SatelliteStatus.DOWNLINKING
                        add_message("GS", f"Downlink report: Job {task.task_id} - FIRE CONFIRMED", "CRIT")
            
            time.sleep(0.5)
        except Exception as e:
            print(f"Sim error: {e}")
            time.sleep(1)

threading.Thread(target=simulation_loop, daemon=True).start()

# --- Telemetry ---
_prev_net = psutil.net_io_counters()
_prev_time = time.time()

def get_telemetry() -> Telemetry:
    global _prev_net, _prev_time
    vm = psutil.virtual_memory()
    batt = psutil.sensors_battery()
    curr_net = psutil.net_io_counters()
    curr_time = time.time()
    dt = curr_time - _prev_time
    rx = (curr_net.bytes_recv - _prev_net.bytes_recv) / (dt * 1024 * 1024) if dt > 0 else 0
    tx = (curr_net.bytes_sent - _prev_net.bytes_sent) / (dt * 1024 * 1024) if dt > 0 else 0
    _prev_net = curr_net; _prev_time = curr_time

    is_ai_active = any(s.get("status") == SatelliteStatus.AI_PROCESSING for s in satellite_dynamic_states.values())
    cpu_adj = random.uniform(20, 40) if is_ai_active else 0
    
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = str(timedelta(seconds=int((datetime.now() - boot_time).total_seconds())))

    return Telemetry(
        cpu_percent=min(100.0, psutil.cpu_percent() + cpu_adj),
        ram_percent=vm.percent,
        temp_c=42.0 + (cpu_adj/2),
        battery_percent=batt.percent if batt else 100.0,
        network_rx=round(rx, 2),
        network_tx=round(tx, 2),
        disk_usage=psutil.disk_usage('/').percent,
        uptime=uptime,
        processes_count=len(psutil.pids()),
        users_count=len(psutil.users()),
        container_status="PBS_INF_ACTIVE" if is_ai_active else "HEALTHY"
    )

@app.route("/")
def index():
    return send_from_directory(str(WEB_DIR), "index.html")

@app.route("/api/state")
def get_state():
    state = GlobalState(
        timestamp=datetime.now(),
        satellites=[Satellite(**s) for s in sat_engine.get_positions(satellite_dynamic_states)],
        fire_zones=fire_zones,
        telemetry=get_telemetry(),
        queue=task_queue,
        messages=messages
    )
    return state.model_dump_json()

@app.route("/api/ignite", methods=["POST"])
def trigger_spike():
    lat = random.uniform(-60, 60)
    lon = random.uniform(-180, 180)
    fz_id = f"FZ-{len(fire_zones)+1}"
    fire_zones.append(FireZone(id=fz_id, lat=lat, lon=lon, intensity=0.8, last_updated=datetime.now()))
    
    assigned_id = sat_engine.get_closest_satellite(lat, lon)
    job_id = f"{1000000 + len(task_queue)}.orbios"
    
    new_task = MissionTask(
        task_id=job_id,
        description=f"Anomaly {fz_id}",
        priority=1,
        status="QUEUED",
        stage=TaskStage.HEAT_DETECTION,
        progress=0.0,
        assigned_satellite_id=assigned_id
    )
    task_queue.append(new_task)
    add_message("GS", f"Job {job_id} submitted to PBS queue 'ai_inference'", "INFO")
    return jsonify({"status": "submitted", "job_id": job_id})

@app.route("/api/clear", methods=["POST"])
def clear_all():
    global fire_zones, task_queue, messages, satellite_dynamic_states
    fire_zones = []; task_queue = []; messages = []; satellite_dynamic_states = {}
    return jsonify({"status": "cleared"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=False)
