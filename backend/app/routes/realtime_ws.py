from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.event_bus import event_bus
import json
import logging
from datetime import datetime

router = APIRouter(tags=["realtime"])
logger = logging.getLogger(__name__)

@router.websocket("/realtime")
async def websocket_endpoint(websocket: WebSocket):
    await event_bus.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "client.hello":
                    await websocket.send_text(json.dumps({
                        "eventType": "server.hello",
                        "payload": {
                            "status": "connected",
                            "serverTime": datetime.now().isoformat()
                        }
                    }))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        event_bus.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        event_bus.disconnect(websocket)
