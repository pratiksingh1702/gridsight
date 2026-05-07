# GridSight FastAPI Backend + UI Integration Prompt

ROLE
You are a senior backend + full-stack engineer. Build a full FastAPI backend for the GridSight 3D UI and integrate it with the existing 3D dashboard.

REQUIRED INPUTS (READ THESE FIRST)
- `index.html` (current 3D UI with mock arrays)
- `REALTIME_BACKEND_INTEGRATION_GUIDE.md` (FastAPI demo guide and endpoints)
- `README.md`, `walkthrough.md`, `core_logic_presentation.md`
- `ai_master_prompt.md`, `grid_sight_full_plan.md`, `grid_build_prompt.md`, `suggestion.md`, `DECISIONS.md`
- `data/` (meter, feeder, weather CSVs) if you want data-backed demo outputs

OBJECTIVE
Deliver a fully working FastAPI backend that powers the 3D UI in `index.html` with real snapshot data and realtime WebSocket updates. The UI is the hero; do not redesign it. Only replace mock data with backend data and realtime updates.

HARD CONSTRAINTS
- Keep the 3D UI intact. Only change data wiring and event handlers in `index.html`.
- Do not remove or downgrade existing UI elements (panels, overlays, hover behavior).
- No external hosted LLMs. No private data leaving local environment.
- Must run locally with simple commands.

DELIVERABLES (FILES TO CREATE)
1) Backend (new folder):
```
backend/
  app/
    main.py
    core/config.py
    core/logging.py
    models/
      schemas.py
    services/
      data_loader.py
      event_bus.py
      realtime.py
      snapshot.py
    routes/
      health.py
      dashboard.py
      zones.py
      alerts.py
      theft.py
      buildings.py
      meters.py
      metrics.py
      actions.py
      realtime_ws.py
  requirements.txt
  Dockerfile
  README.md
```

2) Frontend integration (modify existing file):
- Update `index.html` to load snapshot data from backend and listen to WebSocket events
- Remove all random number based updates and mock arrays once backend is integrated

MINIMUM API CONTRACT
Base path: `/api/v1`

Snapshot routes (must exist):
- `GET /dashboard/summary`
- `GET /zones`
- `GET /alerts?limit=50`
- `GET /theft-cases?status=active`
- `GET /buildings?includeMetrics=true`
- `GET /meters?status=online`
- `GET /metrics/consumption?window=24h`
- `GET /metrics/anomaly-distribution?window=24h`
- `GET /buildings/{buildingId}/history?window=7d`

Actions (demo-safe):
- `POST /actions/dispatch-audit`
- `POST /actions/flag-alert`
- `GET /buildings/{buildingId}/timeline`

Realtime:
- WebSocket at `GET /realtime`
- Accept a `client.hello` JSON message
- Emit event envelopes:
  - `eventId`, `eventType`, `occurredAt`, `payload`

DATA SHAPE (ALIGN WITH EXISTING UI)
Map these to the existing UI sections in `index.html`:
- Zones: name, risk, pct, color, center x/z
- Alerts: type, message, ago/createdAt
- Theft cases: id, zone, est loss, days, status
- Buildings: id, meterId, anomaly, theft, load, voltage, zone, insight, position + size
- Meters: id, x, z, anomaly, voltage, status, reading

DATA STRATEGY (DEMO FIRST)
- Load initial state from CSVs in `data/` where possible
- If fields are missing, generate reasonable demo values (do not randomize every request)
- Keep state in memory for low-latency demo
- Use a background task to emit realtime updates every 2-5 seconds

INDEX.HTML INTEGRATION TASKS
- Replace the current mock arrays (`ZONES`, `ALERTS`, `THEFT_CASES`, `bldgData`, `METERS`) with data from backend
- Add a bootstrapping function:
  - Fetch snapshot endpoints in parallel
  - Populate UI and 3D scene with snapshot data
- Add a realtime client:
  - Connect to `/api/v1/realtime`
  - Send `{ "type": "client.hello", "clientId": "ui-demo" }`
  - On event, update only the affected UI and mesh
- Remove random KPI mutations and set counters from backend summary

ENGINEERING GUIDELINES
- Use Pydantic models for request and response validation
- Separate routes from services
- Add CORS allowing local dev origins
- Provide clear logging for WebSocket connect and broadcast

RUN COMMANDS (MUST INCLUDE)
- Backend: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- Frontend: open `index.html` or serve with a tiny static server

ACCEPTANCE CRITERIA
- The 3D UI loads with backend data (no mock arrays)
- Live updates appear (alert feed, meter states, counters)
- WebSocket reconnects after disconnect
- No console errors in browser

OUTPUT FORMAT
Provide the full code for the backend files and the edits for `index.html`.
Provide a short README with setup steps.
