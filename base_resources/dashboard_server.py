#!/usr/bin/env python3
"""
Mac System Dashboard — Web Server
──────────────────────────────────
Reads dashboard_config.yaml and serves live metrics as JSON.

Install dependencies:
    pip3 install flask psutil pyyaml

Started automatically by launch_dashboard.command.
Visit http://127.0.0.1:5000 once running.
"""

import os, re, sys, time, platform, subprocess
from datetime import datetime, timedelta
from pathlib import Path

# ── Dependency check ─────────────────────────────────────────────────────────

def _require(pkg, import_as=None):
    try:
        __import__(import_as or pkg)
    except ImportError:
        print(f"Missing dependency: {pkg}\n  Run: pip3 install {pkg}")
        sys.exit(1)

_require("flask")
_require("psutil")
_require("pyyaml", "yaml")

import psutil, yaml
from flask import Flask, jsonify, send_from_directory

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE        = Path(__file__).parent
CONFIG_PATH = BASE / "dashboard_config.yaml"
HTML_PATH   = BASE / "dashboard.html"

app = Flask(__name__, static_folder=str(BASE))

# ── Config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

# ── Helpers ───────────────────────────────────────────────────────────────────

def bytes_human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"

# ── Disk I/O rate tracking ────────────────────────────────────────────────────

_prev_io: dict = {"t": None, "r": 0, "w": 0}

def disk_io_rates() -> tuple[float, float]:
    global _prev_io
    io  = psutil.disk_io_counters()
    now = time.time()
    if not io:
        return 0.0, 0.0
    read_rate = write_rate = 0.0
    if _prev_io["t"] is not None:
        dt = now - _prev_io["t"]
        if dt > 0:
            read_rate  = (io.read_bytes  - _prev_io["r"]) / dt
            write_rate = (io.write_bytes - _prev_io["w"]) / dt
    _prev_io = {"t": now, "r": io.read_bytes, "w": io.write_bytes}
    return max(0, read_rate), max(0, write_rate)

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(BASE), "dashboard.html")

@app.route("/config")
def config_route():
    return jsonify(load_config())

@app.route("/metrics")
def metrics():
    cfg    = load_config()
    panels = cfg.get("panels", {})
    data   = {}

    # ── CPU ──────────────────────────────────────────────────────────────────
    pc = panels.get("cpu", {})
    if pc.get("enabled"):
        freq = psutil.cpu_freq()
        try:
            la = list(os.getloadavg())
        except AttributeError:
            la = None
        data["cpu"] = {
            "overall":   round(psutil.cpu_percent(interval=None), 1),
            "per_core":  [round(p, 1) for p in psutil.cpu_percent(percpu=True)],
            "frequency": round(freq.current) if freq else None,
            "freq_max":  round(freq.max)     if freq else None,
            "load_avg":  [round(x, 2) for x in la] if la else None,
        }

    # ── Memory ───────────────────────────────────────────────────────────────
    pm = panels.get("memory", {})
    if pm.get("enabled"):
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        data["memory"] = {
            "percent":       round(vm.percent, 1),
            "used_str":      bytes_human(vm.used),
            "total_str":     bytes_human(vm.total),
            "active":        bytes_human(vm.active)   if hasattr(vm, "active")   else None,
            "inactive":      bytes_human(vm.inactive) if hasattr(vm, "inactive") else None,
            "wired":         bytes_human(vm.wired)    if hasattr(vm, "wired")    else None,
            "swap_percent":  round(sw.percent, 1),
            "swap_used_str": bytes_human(sw.used),
            "swap_total_str":bytes_human(sw.total),
        }

    # ── Battery ───────────────────────────────────────────────────────────────
    pb = panels.get("battery", {})
    if pb.get("enabled"):
        batt = psutil.sensors_battery()
        if batt is None:
            data["battery"] = {"available": False}
        else:
            bd: dict = {
                "available": True,
                "percent":   round(batt.percent, 1),
                "plugged":   batt.power_plugged,
                "secs_left": int(batt.secsleft)
                             if not batt.power_plugged and batt.secsleft > 0
                             else None,
            }
            # macOS extras via system_profiler
            if pb.get("show_cycle_count") or pb.get("show_health"):
                try:
                    raw = subprocess.check_output(
                        ["system_profiler", "SPPowerDataType"],
                        text=True, timeout=4,
                    )
                    for line in raw.splitlines():
                        if pb.get("show_cycle_count") and "Cycle Count" in line:
                            bd["cycle_count"] = line.split(":")[-1].strip()
                        if pb.get("show_health") and "Condition" in line:
                            bd["health"] = line.split(":")[-1].strip()
                except Exception:
                    pass
            data["battery"] = bd

    # ── Disk ──────────────────────────────────────────────────────────────────
    pd = panels.get("disk", {})
    if pd.get("enabled"):
        mounts = pd.get("mounts") or []
        parts  = psutil.disk_partitions()
        if mounts:
            parts = [p for p in parts if p.mountpoint in mounts]
        partitions = []
        for part in parts:
            try:
                u = psutil.disk_usage(part.mountpoint)
                partitions.append({
                    "mount":     part.mountpoint,
                    "percent":   round(u.percent, 1),
                    "used_str":  bytes_human(u.used),
                    "total_str": bytes_human(u.total),
                })
            except PermissionError:
                pass
        rr, wr = disk_io_rates()
        data["disk"] = {
            "partitions":  partitions,
            "read_rate":   bytes_human(rr) + "/s",
            "write_rate":  bytes_human(wr) + "/s",
        }

    # ── Temperature ───────────────────────────────────────────────────────────
    pt = panels.get("temperature", {})
    if pt.get("enabled"):
        temp = None
        try:
            sensors = psutil.sensors_temperatures()
            if sensors:
                for entries in sensors.values():
                    if entries:
                        temp = entries[0].current
                        break
        except AttributeError:
            pass
        if temp is None:
            for cmd in [["osx-cpu-temp"], ["istats", "cpu", "--value-only"]]:
                try:
                    raw = subprocess.check_output(cmd, text=True, timeout=3).strip()
                    m   = re.search(r"[\d.]+", raw)
                    if m:
                        temp = float(m.group())
                        break
                except Exception:
                    pass
        data["temperature"] = {"value": round(temp, 1) if temp is not None else None}

    # ── Processes ─────────────────────────────────────────────────────────────
    pp = panels.get("processes", {})
    if pp.get("enabled"):
        n        = pp.get("top_n", 8)
        sort_by  = pp.get("sort_by", "cpu")
        sort_key = {"cpu": "cpu_percent", "memory": "memory_percent", "name": "name"}.get(
            sort_by, "cpu_percent"
        )
        procs: list = []
        for p in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent"]):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if sort_key != "name":
            procs.sort(key=lambda x: x.get(sort_key) or 0, reverse=True)
        else:
            procs.sort(key=lambda x: (x.get("name") or "").lower())
        data["processes"] = [
            {
                "pid":  p.get("pid"),
                "name": p.get("name", "?"),
                "user": (p.get("username") or "")[:14],
                "cpu":  round(p.get("cpu_percent") or 0, 1),
                "mem":  round(p.get("memory_percent") or 0, 1),
            }
            for p in procs[:n]
        ]

    # ── Users ─────────────────────────────────────────────────────────────────
    pu = panels.get("users", {})
    if pu.get("enabled"):
        data["users"] = [
            {
                "name":     u.name,
                "terminal": u.terminal or "-",
                "since":    datetime.fromtimestamp(u.started).strftime("%H:%M %d %b"),
            }
            for u in psutil.users()
        ]

    # ── System info ───────────────────────────────────────────────────────────
    ps = panels.get("uptime", {})
    if ps.get("enabled"):
        boot   = datetime.fromtimestamp(psutil.boot_time())
        uptime = str(timedelta(seconds=int((datetime.now() - boot).total_seconds())))
        data["sysinfo"] = {
            "hostname":  platform.node(),
            "os":        f"{platform.system()} {platform.release()}",
            "arch":      platform.machine(),
            "boot_time": boot.strftime("%d %b %Y %H:%M"),
            "uptime":    uptime,
            "cpu_count": psutil.cpu_count(logical=True),
        }

    return jsonify(data)

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cfg  = load_config()
    host = cfg.get("server", {}).get("host", "127.0.0.1")
    port = cfg.get("server", {}).get("port", 5000)

    # Warm up CPU percent (first call always returns 0)
    psutil.cpu_percent(percpu=True)
    time.sleep(0.2)

    print(f"Mac Dashboard running at  http://{host}:{port}")
    print(f"Config:                   {CONFIG_PATH}")
    print(f"Log:                      {BASE / '.dashboard.log'}")
    print("Press Ctrl-C to stop.\n")

    app.run(host=host, port=port, debug=False)
