import asyncio
import random
import time
from datetime import datetime
from typing import List, Dict
from app.services.data_loader import get_meters_list, get_zones_from_metadata
from app.services.ai_engine import ai_engine
from app.models.schemas import (
    DashboardSummary, ZoneInfo, AlertItem, TheftCase, MeterSnapshot, BuildingSnapshot
)

class GridSnapshot:
    def __init__(self):
        self.meters: Dict[str, MeterSnapshot] = {}
        self.buildings: Dict[str, BuildingSnapshot] = {}
        self.zones: List[ZoneInfo] = []
        self.alerts: List[AlertItem] = []
        self.theft_cases: List[TheftCase] = []
        self.summary: DashboardSummary = DashboardSummary(
            activeAlerts=0, gridHealthPercent=100.0, totalLoadMw=0.0,
            activeTheftCases=0, onlineMeters=0, aiConfidencePercent=100.0,
            timestamp=datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        )
        self.bootstrapped = False
        # bootstrap() is now called explicitly or handled lazily

    def bootstrap(self):
        # 1. Setup Zones
        zone_names = get_zones_from_metadata()
        colors = ['#c62828', '#c62828', '#e65100', '#e65100', '#e65100', '#2e7d32', '#2e7d32']
        coords = [(25, -18), (-22, 20), (8, 18), (-5, -12), (20, 5), (-25, -8), (-12, 22)]
        
        for i, name in enumerate(zone_names):
            idx = i % len(colors)
            self.zones.append(ZoneInfo(
                name=name,
                risk='h' if idx < 2 else 'm' if idx < 5 else 'l',
                pct=random.randint(20, 90),
                color=colors[idx],
                cx=coords[idx][0],
                cz=coords[idx][1]
            ))
        self.update_summary()
        self.bootstrapped = True

        # 3. Initial Alerts
        self.alerts = [
            AlertItem(type='crit', message='Transformer TF-247 overload — 94% capacity', ago='2m'),
            AlertItem(type='warn', message='Meter tamper — Whitefield Blk C12', ago='11m'),
            AlertItem(type='info', message='AI: Zone 3 outage risk 82%, 6h window', ago='47m'),
        ]

        # 4. Theft Cases
        self.theft_cases = [
            TheftCase(id='TH-0041', zone='Whitefield', estLoss='₹28,400/mo', days=17, status='Active'),
            TheftCase(id='TH-0038', zone='Koramangala', estLoss='₹14,200/mo', days=8, status='Active'),
        ]

        # 5. Summary
        self.update_summary()

    def update_summary(self):
        self.summary = DashboardSummary(
            activeAlerts=len([a for a in self.alerts if a.type == 'crit']),
            gridHealthPercent=87.4,
            totalLoadMw=23.41,
            activeTheftCases=len(self.theft_cases),
            onlineMeters=len(self.meters),
            aiConfidencePercent=93.7,
            timestamp=datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        )

    async def full_bootstrap(self):
        """Heavy lifting done in background."""
        if not self.zones:
            self.bootstrap()
            
        # Setup Meters & Buildings
        meter_ids = get_meters_list()[:200] 
        for i, mid in enumerate(meter_ids):
            z = self.zones[i % len(self.zones)]
            
            mx = (random.random() - 0.5) * 90
            mz = (random.random() - 0.5) * 90
            m = MeterSnapshot(
                meterId=mid, x=mx, z=mz,
                anomalyScore=random.randint(0, 100),
                voltage=random.randint(220, 240),
                status=random.choice(["Normal", "Normal", "Normal", "Alert", "Fault"]),
                lastReadingKwh=random.uniform(100, 500)
            )
            self.meters[mid] = m

            b = BuildingSnapshot(
                buildingId=f"BLD-{i:04d}", meterId=mid,
                anomaly=m.anomalyScore, theft=random.randint(0, 70),
                load=random.randint(40, 300), voltage=m.voltage,
                zone=z.name, insight="AI: Analyzing...",
                x=mx + random.uniform(-2, 2), z=mz + random.uniform(-2, 2),
                width=2 + random.uniform(0, 2), depth=2 + random.uniform(0, 2),
                height=5 + random.uniform(0, 15)
            )
            
            # Real AI for first 5 (DISABLED ON BOOTSTRAP TO PREVENT CLOUD OOM)
            # The AI Engine can still be queried via REST, but we avoid concurrent 
            # heavy Prophet fitting during the initial server startup.
            if i < 5:
                # Fallback to simulated insights for startup speed
                b.insight = "AI: Anomaly detected (Simulated due to memory limits)"
                b.theft = 85.0
            
            self.buildings[b.buildingId] = b
            # Yield control occasionally
            if i % 20 == 0: await asyncio.sleep(0)

        self.update_summary()

    def get_snapshot(self):
        return {
            "summary": self.summary,
            "zones": self.zones,
            "meters": list(self.meters.values()),
            "buildings": list(self.buildings.values()),
            "alerts": self.alerts,
            "theft_cases": self.theft_cases
        }

grid_snapshot = GridSnapshot()
