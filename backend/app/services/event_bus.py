import asyncio
import json
import uuid
from datetime import datetime
from typing import Set
from fastapi import WebSocket
from app.services.snapshot import grid_snapshot
from app.models.schemas import RealtimeEvent, AlertItem

class EventBus:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, event: RealtimeEvent):
        message = event.json()
        to_remove = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                to_remove.append(connection)
        
        for conn in to_remove:
            self.active_connections.discard(conn)

    async def start_simulation(self):
        """Background task to simulate grid events."""
        while True:
            await asyncio.sleep(8) # Every 8 seconds
            
            # Simulate a meter update
            import random
            meter_ids = list(grid_snapshot.meters.keys())
            if not meter_ids: continue
            
            mid = random.choice(meter_ids)
            meter = grid_snapshot.meters[mid]
            
            # Update meter state
            meter.voltage = 230 + random.uniform(-5, 5)
            meter.anomalyScore = random.randint(0, 100)
            if meter.anomalyScore > 80:
                meter.status = "Alert"
            else:
                meter.status = "Normal"
            
            event = RealtimeEvent(
                eventId=str(uuid.uuid4()),
                eventType="meter.updated",
                occurredAt=datetime.now().isoformat(),
                payload={
                    "meterId": mid,
                    "status": meter.status,
                    "voltage": meter.voltage,
                    "anomalyScore": meter.anomalyScore
                }
            )
            await self.broadcast(event)

            # Occasionally add an alert
            if random.random() < 0.3:
                alert = AlertItem(
                    type=random.choice(["crit", "warn", "info"]),
                    message=f"AI Alert: Anomaly detected at {mid}",
                    createdAt=datetime.now().isoformat(),
                    ago="now"
                )
                grid_snapshot.alerts.insert(0, alert)
                grid_snapshot.alerts = grid_snapshot.alerts[:20] # Keep last 20
                
                alert_event = RealtimeEvent(
                    eventId=str(uuid.uuid4()),
                    eventType="alert.new",
                    occurredAt=datetime.now().isoformat(),
                    payload=alert
                )
                await self.broadcast(alert_event)

event_bus = EventBus()
