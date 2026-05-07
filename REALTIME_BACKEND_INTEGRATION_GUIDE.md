# GridSight AI — FastAPI Demo Backend Integration Guide

This focused guide shows how to implement a simple demo backend using FastAPI so the existing 3D UI receives snapshots and streaming updates. It's intentionally minimal for rapid demo purposes (no DB, in-memory state, easy-to-run). Use this as a reference to evolve into a production service.

Goals for the demo
- Provide snapshot endpoints used by the UI
- Provide a WebSocket-based realtime stream (with simple subscribe handshake)
- Keep implementation minimal so you can run the backend quickly for demos

Prerequisites
- Python 3.10+ (recommended)
- Create and activate a venv in the project root

Install requirements (example):

```bash
python -m venv .venv
.\\.venv\\Scripts\\activate
pip install fastapi uvicorn websockets
```

Optional for SSE fallback:

```bash
pip install sse-starlette
```

Quick project layout (backend/demo):

backend/
- app.py               # FastAPI app (snapshots + websocket demo)
- requirements.txt
- Dockerfile

Core design (demo)
- Snapshot endpoints: `/api/v1/dashboard/summary`, `/api/v1/zones`, `/api/v1/buildings`, `/api/v1/meters`, `/api/v1/alerts`, `/api/v1/theft-cases`
- WebSocket: `/api/v1/realtime` — clients send a simple `client.hello` JSON to subscribe; server pushes event envelopes
- Event envelope (JSON): `{ "eventId": "<id>", "eventType": "meter.updated", "occurredAt": "<ISO>", "payload": {...} }`

Minimal FastAPI example (app.py)

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import asyncio, json, time, uuid

app = FastAPI()

# In-memory demo state (small subset)
STATE = {
    "summary": {"activeAlerts": 3, "gridHealthPercent": 87.2, "totalLoadMw": 34.1, "activeTheftCases": 2, "onlineMeters": 58, "aiConfidencePercent": 92.1, "timestamp": None},
    "zones": [],
    "buildings": [],
    "meters": [],
    "alerts": [],
}

def now_iso():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

@app.get('/api/v1/dashboard/summary')
async def get_summary():
    s = STATE['summary'].copy()
    s['timestamp'] = now_iso()
    return JSONResponse(s)

@app.get('/api/v1/meters')
async def get_meters():
    return JSONResponse(STATE['meters'])

@app.get('/api/v1/buildings')
async def get_buildings():
    return JSONResponse(STATE['buildings'])

# Very small WebSocket broadcast manager for demo
class Broadcaster:
    def __init__(self):
        self._ws = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._ws.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self._ws.discard(websocket)

    async def broadcast(self, message: str):
        to_remove = []
        for ws in list(self._ws):
            try:
                await ws.send_text(message)
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            self._ws.discard(ws)

BR = Broadcaster()

@app.websocket('/api/v1/realtime')
async def websocket_endpoint(websocket: WebSocket):
    await BR.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Expect a small hello message from client to start
            try:
                obj = json.loads(data)
            except Exception:
                obj = {}
            if obj.get('type') == 'client.hello':
                # reply with a simple confirmation
                await websocket.send_text(json.dumps({'eventType':'server.hello','payload':{'serverTime':now_iso()}}))
    except WebSocketDisconnect:
        BR.disconnect(websocket)

# Background demo task that periodically broadcasts a fake meter.updated event
async def demo_pusher():
    while True:
        await asyncio.sleep(3)
        evt = {
            'eventId': str(uuid.uuid4()),
            'eventType': 'meter.updated',
            'occurredAt': now_iso(),
            'payload': {
                'meterId': 'MTR-5001', 'status': 'Normal', 'anomalyScore': 12, 'voltage': 230, 'lastReadingKwh': 192.3, 'updatedAt': now_iso()
            }
        }
        await BR.broadcast(json.dumps(evt))

@app.on_event('startup')
async def startup_event():
    # populate tiny demo data
    STATE['meters'] = [{'meterId':f'MTR-{5000+i}', 'x':0, 'z':0, 'status':'Normal','anomalyScore':0,'voltage':230, 'lastReadingKwh':100+i} for i in range(20)]
    STATE['buildings'] = [{'buildingId':f'BLD-{i}', 'x':(i%5)*4, 'z':(i//5)*4, 'width':2,'depth':2,'height':5+ (i%6), 'anomalyScore': (i*7)%100, 'theftProbability': (i*5)%100} for i in range(30)]
    asyncio.create_task(demo_pusher())

```

How the UI should use this demo server
- On load: `GET /api/v1/dashboard/summary`, `GET /api/v1/zones`, `GET /api/v1/buildings`, `GET /api/v1/meters`, `GET /api/v1/alerts`
- Realtime: open a WebSocket to `/api/v1/realtime` and send `{ "type": "client.hello", "clientId":"demo-client" }` then listen for event envelopes
- On reconnect: re-fetch `/api/v1/dashboard/summary` to rehydrate UI

Run the demo server

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Dockerfile (quick demo)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir fastapi uvicorn
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8000"]
```

Security & limits for demo
- Demo keeps state in memory — not for production
- If you want auth for demo, add a simple API key header check in endpoints and require that header in the UI WebSocket handshake

Evolving to production
- Replace in-memory structures with a proper DB (TimescaleDB, Postgres) for snapshots and Redis / Kafka for event buses
- Add JWT-based auth, role checks for action routes
- Add monotonic event IDs and replay windows for missed events
- Add monitoring, rate limits, and proper error schema

Notes and mapping to current UI
- The UI snapshot and event shapes in the original guide remain valid; this file now provides concrete FastAPI demo code and run instructions you can start with immediately.

Next steps I can take for you
- Scaffold the `backend/` folder and add `app.py`, `requirements.txt`, and a `Dockerfile` ready to run
- Add a small README with run commands

If you want me to scaffold the demo files now, tell me and I will create them in `backend/` and run the linter/quick smoke run.
