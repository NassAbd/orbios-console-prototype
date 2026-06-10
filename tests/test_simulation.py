import sys
from pathlib import Path

# Add project root and part folders to path so we can import modules
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
for path in [PROJECT_ROOT, PROJECT_ROOT / "workstation_part", PROJECT_ROOT / "pi_part"]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

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
    res = parse_lat_lon_type("OIL_LEAK_LAT38.500_LON-9.500.dat")
    assert res is not None
    lat, lon, alert_type = res
    assert lat == 38.500
    assert lon == -9.500
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
        output_dir = PROJECT_ROOT / "pi_part" / "algo_part" / "output"
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
        assert 0 <= validated.cpu.overall <= 100
        assert validated.temperature.value is None or validated.temperature.value > 0
        if validated.battery.available:
            assert validated.battery.percent is not None
            assert 0 <= validated.battery.percent <= 100
            assert isinstance(validated.battery.plugged, bool)


def test_update_telemetry_static():
    # Verify update_telemetry returns idle coordinates when not active
    from orbios_sim import update_telemetry
    res = update_telemetry()
    assert res["lat"] == 44.5000
    assert res["lon"] == -2.0000
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
    orbios_sim.handle_new_output_file("OIL_LEAK_LAT38.500_LON-9.500.dat")
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


def test_new_button_signals(tmp_path, monkeypatch):
    import orbios_sim
    
    # Mock paths
    monkeypatch.setattr(orbios_sim, "MISSION", tmp_path)
    monkeypatch.setattr(orbios_sim, "OUTPUT_DIR", tmp_path)
    
    # Reset latched states
    orbios_sim.STATE["latched_states"] = {k: False for k in orbios_sim.LATCH_MSGS}
    
    # 1. Test instantaneous commands
    calc_file = tmp_path / "STAR_TRACKER_CALC_20260601_220000"
    calc_file.touch()
    purge_file = tmp_path / "THRUSTER_PURGE_20260601_220000"
    purge_file.touch()
    
    # Run the processing logic that unlinks these files
    if orbios_sim.MISSION.exists():
        for f in list(orbios_sim.MISSION.iterdir()):
            fname = f.name
            if fname.startswith("STAR_TRACKER_CALC"):
                dat_file = orbios_sim.BUTTON_DAT_FILES.get("STAR_TRACKER_CALC")
                if dat_file:
                    orbios_sim.touch_output_file(dat_file)
                try:
                    f.unlink()
                except Exception:
                    pass
            elif fname.startswith("THRUSTER_PURGE"):
                dat_file = orbios_sim.BUTTON_DAT_FILES.get("THRUSTER_PURGE")
                if dat_file:
                    orbios_sim.touch_output_file(dat_file)
                try:
                    f.unlink()
                except Exception:
                    pass

                
    assert not calc_file.exists()
    assert not purge_file.exists()
    assert (tmp_path / "Star_tracker_attitude_extraction.dat").exists()
    assert (tmp_path / "Thruster_purge.dat").exists()
    
    # Clean up output files
    (tmp_path / "Star_tracker_attitude_extraction.dat").unlink()
    (tmp_path / "Thruster_purge.dat").unlink()
    
    # 2. Test latched states transition
    # Latch BATT_HEATER_ON
    heater_file = tmp_path / "BATT_HEATER_ON_20260601_220000"
    heater_file.touch()
    
    # Simulate processing step 6b
    current_files = [f.name for f in list(orbios_sim.MISSION.iterdir())]
    for state_name, (on_msg, off_msg) in orbios_sim.LATCH_MSGS.items():
        is_active = any(name.startswith(state_name) for name in current_files)
        was_active = orbios_sim.STATE["latched_states"].get(state_name, False)
        dat_file = orbios_sim.BUTTON_DAT_FILES.get(state_name)
        if is_active and not was_active:
            orbios_sim.STATE["latched_states"][state_name] = True
            if dat_file:
                orbios_sim.touch_output_file(dat_file)
        elif not is_active and was_active:
            orbios_sim.STATE["latched_states"][state_name] = False
            if dat_file:
                orbios_sim.remove_output_file(dat_file)
            
    assert orbios_sim.STATE["latched_states"]["BATT_HEATER_ON"] is True
    assert (tmp_path / "Battery_heater_on.dat").exists()
    
    # Release BATT_HEATER_ON (delete file)
    heater_file.unlink()
    
    # Re-simulate processing step 6b
    current_files = [f.name for f in list(orbios_sim.MISSION.iterdir())]
    for state_name, (on_msg, off_msg) in orbios_sim.LATCH_MSGS.items():
        is_active = any(name.startswith(state_name) for name in current_files)
        was_active = orbios_sim.STATE["latched_states"].get(state_name, False)
        dat_file = orbios_sim.BUTTON_DAT_FILES.get(state_name)
        if is_active and not was_active:
            orbios_sim.STATE["latched_states"][state_name] = True
            if dat_file:
                orbios_sim.touch_output_file(dat_file)
        elif not is_active and was_active:
            orbios_sim.STATE["latched_states"][state_name] = False
            if dat_file:
                orbios_sim.remove_output_file(dat_file)
            
    assert orbios_sim.STATE["latched_states"]["BATT_HEATER_ON"] is False
    assert not (tmp_path / "Battery_heater_on.dat").exists()


