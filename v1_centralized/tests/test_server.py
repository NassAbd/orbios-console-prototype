import pytest
from src.server.schema import GlobalState, Telemetry
from datetime import datetime

def test_telemetry_schema():
    data = {
        "cpu_percent": 10.5,
        "ram_percent": 50.0,
        "temp_c": 45.0,
        "battery_percent": 90.0,
        "container_status": "HEALTHY"
    }
    telemetry = Telemetry(**data)
    assert telemetry.cpu_percent == 10.5
    assert telemetry.container_status == "HEALTHY"

def test_global_state_schema():
    data = {
        "timestamp": datetime.now(),
        "satellites": [],
        "fire_zones": [],
        "telemetry": {
            "cpu_percent": 10.5,
            "ram_percent": 50.0,
            "temp_c": 45.0,
            "battery_percent": 90.0,
            "container_status": "HEALTHY"
        },
        "queue": []
    }
    state = GlobalState(**data)
    assert len(state.satellites) == 0
    assert state.telemetry.temp_c == 45.0
