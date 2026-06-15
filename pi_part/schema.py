from typing import List, Optional

from pydantic import BaseModel, Field


class SatelliteTelemetry(BaseModel):
    id: str
    lat: float
    lon: float
    alt_km: float
    timestamp: str

class MissionAlert(BaseModel):
    type: str = Field(..., description="HEAT_ANOMALY, WILDFIRE, or OIL_LEAK")
    lat: float
    lon: float
    intensity: float
    status: str = Field(..., description="DETECTED or CONFIRMED")
    alert_msg: Optional[str] = None

class ProcessInfo(BaseModel):
    pid: int
    name: str
    user: str
    cpu: float
    mem: float

class OpenPBSJob(BaseModel):
    job_id: str
    task: str
    status: str
    node: str
    progress: int
    ticks: int

class CpuMetrics(BaseModel):
    overall: float
    per_core: List[float]
    frequency: Optional[int] = None
    freq_max: Optional[int] = None
    load_avg: Optional[List[float]] = None

class MemoryMetrics(BaseModel):
    percent: float
    used_str: str
    total_str: str
    active: Optional[str] = None
    inactive: Optional[str] = None
    wired: Optional[str] = None
    swap_percent: float
    swap_used_str: str
    swap_total_str: str

class BatteryMetrics(BaseModel):
    available: bool
    percent: Optional[float] = None
    plugged: Optional[bool] = None
    secs_left: Optional[int] = None
    cycle_count: Optional[str] = None
    health: Optional[str] = None

class DiskPartition(BaseModel):
    mount: str
    percent: float
    used_str: str
    total_str: str

class DiskMetrics(BaseModel):
    partitions: List[DiskPartition]
    read_rate: str
    write_rate: str

class TemperatureMetrics(BaseModel):
    value: Optional[float] = None

class UserInfo(BaseModel):
    name: str
    terminal: str
    since: str

class SysInfoMetrics(BaseModel):
    hostname: str
    os: str
    arch: str
    boot_time: str
    uptime: str
    cpu_count: int

class WildfireAlertStatus(BaseModel):
    active: bool
    data: Optional[MissionAlert] = None

class SystemMetricsResponse(BaseModel):
    cpu: CpuMetrics
    memory: MemoryMetrics
    battery: BatteryMetrics
    disk: DiskMetrics
    temperature: TemperatureMetrics
    processes: List[ProcessInfo]
    users: List[UserInfo]
    sysinfo: SysInfoMetrics
    wildfire_alert: WildfireAlertStatus
    pbs_queue: List[OpenPBSJob]


class FileTouchRequest(BaseModel):
    dir: str
    name: str


class FileRemoveRequest(BaseModel):
    dir: str
    name: str


class FileListRequest(BaseModel):
    dir: str


class FileTouchResponse(BaseModel):
    ok: bool
    path: Optional[str] = None
    error: Optional[str] = None


class FileRemoveResponse(BaseModel):
    ok: bool
    error: Optional[str] = None


class FileListResponse(BaseModel):
    files: List[str]
    error: Optional[str] = None

