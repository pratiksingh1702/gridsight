from fastapi import APIRouter
from app.services.snapshot import grid_snapshot
from app.models.schemas import MeterSnapshot
from typing import List

router = APIRouter(prefix="/meters", tags=["meters"])

@router.get("", response_model=List[MeterSnapshot])
async def get_meters(status: str = None):
    meters = list(grid_snapshot.meters.values())
    if status:
        meters = [m for m in meters if m.status.lower() == status.lower()]
    return meters

@router.get("/{meter_id}", response_model=MeterSnapshot)
async def get_meter(meter_id: str):
    return grid_snapshot.meters.get(meter_id)
