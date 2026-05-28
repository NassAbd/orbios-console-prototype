import sys
from pathlib import Path

# Add project root to path so we can import modules
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orbios_sim import parse_lat_lon_type  # noqa: E402
from schema import SystemMetricsResponse  # noqa: E402

def test_parse_lat_lon_type():
    # Wildfire filename parsing
    res = parse_lat_lon_type("WILDFIRE_LAT41.458_LON-7.782.dat")
    assert res is not None
    lat, lon, alert_type = res
    assert lat == 41.458
    assert lon == -7.782
    assert alert_type == "WILDFIRE"

    # False alert filename parsing
    res = parse_lat_lon_type("FALSE_ALERT_LAT37.142_LON-8.799.dat")
    assert res is not None
    lat, lon, alert_type = res
    assert lat == 37.142
    assert lon == -8.799
    assert alert_type == "FALSE_ALERT"

    # Oil leak filename parsing
    res = parse_lat_lon_type("OIL_LEAK_LAT41.122_LON-8.895.dat")
    assert res is not None
    lat, lon, alert_type = res
    assert lat == 41.122
    assert lon == -8.895
    assert alert_type == "OIL_LEAK"

    # Invalid filename parsing
    assert parse_lat_lon_type("invalid_filename.dat") is None


def test_dashboard_metrics_schema_idle():
    # Test building and validating system metrics response structure
    from dashboard_server import metrics  # noqa: E402
    import flask

    app = flask.Flask(__name__)
    with app.test_request_context():
        # Clean/mock output dir to show 0 files (IDLE phase)
        output_dir = PROJECT_ROOT / "algo_part" / "output"
        if output_dir.exists():
            for f in output_dir.iterdir():
                if f.name.endswith(".dat"):
                    try:
                        f.unlink()
                    except Exception:
                        pass

        response = metrics()
        # Decode json
        data = response.get_json()

        # Verify schema validation succeeds
        validated = SystemMetricsResponse.model_validate(data)
        assert validated.sysinfo.uptime == "IDLE"
        assert validated.cpu.overall == 4.2
        assert validated.temperature.value == 38.5
        assert validated.battery.percent == 98.0
        assert validated.battery.plugged is True


def test_update_telemetry_static():
    # Verify update_telemetry returns static Spain/Portugal coordinates
    from orbios_sim import update_telemetry
    res = update_telemetry()
    assert res["lat"] == 40.2000
    assert res["lon"] == -7.8000
    assert res["alt_km"] == 420.0


def test_alert_auto_clear_logic(tmp_path, monkeypatch):
    import time
    import orbios_sim
    
    # Mock paths in orbios_sim to use tmp_path
    monkeypatch.setattr(orbios_sim, "MISSION", tmp_path)
    
    # Initialize state
    orbios_sim.STATE["active_alerts"] = []
    
    # Mock time.time to return a fixed time
    current_time = 1000.0
    monkeypatch.setattr(time, "time", lambda: current_time)
    
    # Process a wildfire output file
    orbios_sim.handle_new_output_file("WILDFIRE_LAT40.200_LON-7.800.dat")
    
    # Check that FIRE_CONFIRMED.json was created and added to active_alerts
    fire_file = tmp_path / "FIRE_CONFIRMED.json"
    assert fire_file.exists()
    assert len(orbios_sim.STATE["active_alerts"]) == 1
    alert_record = orbios_sim.STATE["active_alerts"][0]
    assert alert_record["path"] == str(fire_file)
    assert alert_record["expires_at"] == 1003.0
    
    # Process an oil leak output file
    orbios_sim.handle_new_output_file("OIL_LEAK_LAT41.122_LON-8.895.dat")
    oil_file = tmp_path / "OIL_LEAK_ACTIVE.json"
    assert oil_file.exists()
    assert len(orbios_sim.STATE["active_alerts"]) == 2
    
    # Call check_and_clear_expired_alerts at current_time=1000.0 (no expiration)
    orbios_sim.check_and_clear_expired_alerts()
    assert fire_file.exists()
    assert oil_file.exists()
    assert len(orbios_sim.STATE["active_alerts"]) == 2
    
    # Advance time to 1003.1 (both expired)
    current_time = 1003.1
    orbios_sim.check_and_clear_expired_alerts()
    
    # Check that both files are deleted and active_alerts is cleared
    assert not fire_file.exists()
    assert not oil_file.exists()
    assert len(orbios_sim.STATE["active_alerts"]) == 0

