from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class SatelliteStatus(str, Enum):
    IDLE = "IDLE"
    IMAGING = "IMAGING"
    AI_PROCESSING = "AI_PROCESSING"
    DOWNLINKING = "DOWNLINKING"
    ERROR = "ERROR"

class TaskStage(str, Enum):
    HEAT_DETECTION = "HEAT_DETECTION"
    IMAGING_ACQUISITION = "IMAGING_ACQUISITION"
    AI_INFERENCE = "AI_INFERENCE"
    GS_REPORTING = "GS_REPORTING"
    COMPLETED = "COMPLETED"

class CommMessage(BaseModel):
    timestamp: datetime
    origin: str  # GS, SAT, AI
    payload: str
    level: str = "INFO" # INFO, WARN, CRIT

class Satellite(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    alt: float
    status: SatelliteStatus = SatelliteStatus.IDLE
    current_task_id: Optional[str] = None

class FireZone(BaseModel):
    id: str
    lat: float
    lon: float
    intensity: float
    status: str = "DETECTED"
    last_updated: datetime

class Telemetry(BaseModel):
    cpu_percent: float
    ram_percent: float
    temp_c: float
    battery_percent: float
    network_rx: float
    network_tx: float
    disk_usage: float
    uptime: str
    processes_count: int
    users_count: int
    container_status: str = "HEALTHY"

class MissionTask(BaseModel):
    task_id: str
    description: str
    priority: int
    status: str = "QUEUED"
    stage: TaskStage = TaskStage.HEAT_DETECTION
    progress: float = 0.0 # 0 to 100
    assigned_satellite_id: Optional[int] = None

class GlobalState(BaseModel):
    timestamp: datetime
    satellites: List[Satellite]
    fire_zones: List[FireZone]
    telemetry: Telemetry
    queue: List[MissionTask]
    messages: List[CommMessage]
