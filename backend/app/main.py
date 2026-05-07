import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import dashboard, meters, buildings, realtime_ws
from app.services.event_bus import event_bus
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(dashboard.router, prefix=settings.API_V1_STR)
app.include_router(meters.router, prefix=settings.API_V1_STR)
app.include_router(buildings.router, prefix=settings.API_V1_STR)
app.include_router(realtime_ws.router, prefix=settings.API_V1_STR)

@app.get("/api/v1/full-report", tags=["Reports"], summary="Download Full Grid Intelligence Report")
async def root_report_download():
    """
    Generates and downloads a comprehensive Markdown report containing:
    - Executive Grid Summary
    - Zone Risk Index
    - AI Alert History
    - Building Anomaly Audit
    - Neural Architecture (Active AI Agents)
    """
    from app.routes.dashboard import download_full_report
    return await download_full_report()

@app.on_event("startup")
async def startup_event():
    # 1. Start the simulation background task
    asyncio.create_task(event_bus.start_simulation())
    # 2. Start the heavy grid bootstrap task
    from app.services.snapshot import grid_snapshot
    asyncio.create_task(grid_snapshot.full_bootstrap())

@app.get("/")
async def root():
    return {"message": "GridSight AI Backend is running", "version": "1.0.0"}
