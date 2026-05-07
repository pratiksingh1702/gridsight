from fastapi import APIRouter
from app.services.snapshot import grid_snapshot
from app.models.schemas import BuildingSnapshot
from typing import List

router = APIRouter(prefix="/buildings", tags=["buildings"])

@router.get("", response_model=List[BuildingSnapshot])
async def get_buildings(includeMetrics: bool = True):
    return list(grid_snapshot.buildings.values())

@router.get("/{building_id}", response_model=BuildingSnapshot)
async def get_building(building_id: str):
    return grid_snapshot.buildings.get(building_id)
