from pydantic import BaseModel, Field
from typing import List, Optional

class Panel(BaseModel):
    name: str
    voltage: str = Field(..., description="e.g., 480Y/277V or 208Y/120V")
    bus_amperes: int

class Load(BaseModel):
    name: str
    kva: float
    panel: str

class OneLineRequest(BaseModel):
    project: str
    service_voltage: str = "480Y/277V"
    service_amperes: int = 2000
    panels: List[Panel]
    loads: List[Load] = []

class Room(BaseModel):
    name: str
    x: float
    y: float
    w: float
    h: float

class Device(BaseModel):
    tag: str
    x: float
    y: float
    notes: Optional[str] = None

class PlanRequest(BaseModel):
    project: str
    rooms: List[Room]
    devices: List[Device] = []
