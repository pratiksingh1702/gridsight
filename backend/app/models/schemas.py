from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

class DashboardSummary(BaseModel):
    activeAlerts: int
    gridHealthPercent: float
    totalLoadMw: float
    activeTheftCases: int
    onlineMeters: int
    aiConfidencePercent: float
    timestamp: str

class ZoneInfo(BaseModel):
    name: str
    risk: str  # 'h', 'm', 'l'
    pct: float
    color: str
    cx: float
    cz: float

class AlertItem(BaseModel):
    id: Optional[str] = None
    type: str  # 'crit', 'warn', 'info'
    message: str
    ago: Optional[str] = None
    createdAt: Optional[str] = None

class TheftCase(BaseModel):
    id: str
    zone: str
    estLoss: str
    days: int
    status: str

class MeterSnapshot(BaseModel):
    meterId: str
    x: float
    z: float
    anomalyScore: float
    voltage: float
    status: str
    lastReadingKwh: Optional[float] = None

class BuildingSnapshot(BaseModel):
    buildingId: str
    meterId: str
    anomaly: float
    theft: float
    load: float
    voltage: float
    zone: str
    insight: str
    x: float
    z: float
    width: float
    depth: float
    height: float

class RealtimeEvent(BaseModel):
    eventId: str
    eventType: str
    occurredAt: str
    payload: Dict[str, Any]

class ActionResponse(BaseModel):
    status: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
