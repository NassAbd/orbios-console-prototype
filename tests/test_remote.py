import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root and part folders to path
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
for path in [PROJECT_ROOT, PROJECT_ROOT / "workstation_part", PROJECT_ROOT / "pi_part"]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from schema import SystemMetricsResponse  # noqa: E402

# 1. Test Raspberry Pi metrics collection logic
@patch("psutil.cpu_percent")
@patch("psutil.cpu_count")
@patch("psutil.cpu_freq")
@patch("psutil.virtual_memory")
@patch("psutil.swap_memory")
@patch("psutil.disk_usage")
@patch("psutil.sensors_battery", create=True)
@patch("psutil.sensors_temperatures", create=True)
@patch("psutil.process_iter")
@patch("psutil.users")
@patch("psutil.boot_time")
@patch("socket.gethostname")
@patch("platform.system")
@patch("platform.release")
@patch("platform.machine")
def test_pi_metrics_collection(
    mock_machine, mock_release, mock_system, mock_hostname,
    mock_boot_time, mock_users, mock_proc_iter, mock_temp, mock_batt, mock_disk,
    mock_swap, mock_vmem, mock_cpu_freq, mock_cpu_count, mock_cpu_percent
):
    # Setup mocks for 4-core Pi
    mock_cpu_percent.side_effect = [15.2, [10.0, 20.0, 15.0, 16.0]]
    mock_cpu_count.return_value = 4
    
    mock_freq = MagicMock()
    mock_freq.current = 1500.0
    mock_freq.max = 1500.0
    mock_cpu_freq.return_value = mock_freq
    
    mock_vmem.return_value = MagicMock(
        percent=45.5, used=1.8 * 1024**3, total=4.0 * 1024**3,
        active=1.0 * 1024**3, inactive=0.5 * 1024**3, buffers=0.1 * 1024**3, cached=0.2 * 1024**3
    )
    mock_swap.return_value = MagicMock(percent=5.0, used=50 * 1024**2, total=1.0 * 1024**3)
    mock_disk.return_value = MagicMock(percent=35.0, used=10.0 * 1024**3, total=32.0 * 1024**3)
    mock_batt.return_value = None  # Pi doesn't have battery
    
    # Mock thermal sensors
    mock_temp.return_value = {
        "cpu_thermal": [MagicMock(current=52.5)]
    }
    
    # Mock processes
    proc1 = MagicMock()
    proc1.info = {"pid": 1024, "name": "main2", "username": "root", "cpu_percent": 85.0, "memory_percent": 5.2}
    proc2 = MagicMock()
    proc2.info = {"pid": 1, "name": "systemd", "username": "root", "cpu_percent": 0.1, "memory_percent": 0.2}
    mock_proc_iter.return_value = [proc1, proc2]
    
    # Mock users and system info
    user = MagicMock()
    user.name = "pi"
    user.terminal = "pts/0"
    user.started = 1717000000.0
    mock_users.return_value = [user]
    
    mock_boot_time.return_value = 1717000000.0
    mock_hostname.return_value = "raspberrypi"
    mock_system.return_value = "Linux"
    mock_release.return_value = "6.1.0-rpi8-rpi-v8"
    mock_machine.return_value = "aarch64"
    
    # Import the metrics collector function
    from orbios_sim import collect_pi_metrics
    
    with patch("time.time", return_value=1717036000.0):
        metrics_dict = collect_pi_metrics()
        
    validated = SystemMetricsResponse.model_validate(metrics_dict)
    assert validated.sysinfo.cpu_count == 4
    assert validated.sysinfo.hostname == "raspberrypi"
    assert validated.cpu.overall == 15.2
    assert validated.cpu.per_core == [10.0, 20.0, 15.0, 16.0]
    assert validated.temperature.value == 52.5
    assert validated.battery.available is False
    assert any(p.name == "main2" for p in validated.processes)


# 2. Test Workstation Dashboard Server proxying metrics in Remote Mode
@patch("requests.get")
def test_dashboard_proxy_metrics(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "cpu": {"overall": 10.0, "per_core": [10.0, 10.0, 10.0, 10.0], "frequency": 1500, "freq_max": 1500, "load_avg": [0.1, 0.2, 0.3]},
        "memory": {"percent": 50.0, "used_str": "2.0 GB", "total_str": "4.0 GB", "swap_percent": 0.0, "swap_used_str": "0 B", "swap_total_str": "0 B"},
        "battery": {"available": False},
        "disk": {"partitions": [{"mount": "/", "percent": 30.0, "used_str": "10 GB", "total_str": "32 GB"}], "read_rate": "0 B/s", "write_rate": "0 B/s"},
        "temperature": {"value": 45.0},
        "processes": [],
        "users": [],
        "sysinfo": {"hostname": "raspberrypi", "os": "Linux", "arch": "aarch64", "boot_time": "May 28 08:00", "uptime": "IDLE", "cpu_count": 4},
        "wildfire_alert": {"active": False},
        "pbs_queue": []
    }
    mock_get.return_value = mock_response

    import dashboard_server
    with patch.object(dashboard_server, "PI_REMOTE_ENABLED", True), \
         patch.object(dashboard_server, "PI_IP", "192.168.2.2"), \
         patch.object(dashboard_server, "PI_PORT", 5006):
        
        with dashboard_server.app.test_client() as client:
            r = client.get("/metrics")
            assert r.status_code == 200
            data = r.get_json()
            assert data["cpu"]["overall"] == 10.0
            assert data["sysinfo"]["hostname"] == "raspberrypi"
            mock_get.assert_called_with("http://192.168.2.2:5006/api/metrics", timeout=3.0)



# 3. Test startup connection validation block
@patch("requests.get")
def test_dashboard_startup_check_pi_unreachable(mock_get):
    import requests
    mock_get.side_effect = requests.exceptions.ConnectionError("Could not connect to Pi")
    
    from dashboard_server import verify_pi_connection
    with pytest.raises(SystemExit):
        verify_pi_connection("192.168.2.2", 5006)
