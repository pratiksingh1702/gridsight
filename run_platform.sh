#!/bin/bash
echo "=========================================="
echo "GridSight 3D Platform Launcher (Unix)"
echo "=========================================="

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 not found. Please install Python to continue."
    exit 1
fi

echo "[1/4] Installing backend dependencies..."
python3 -m pip install -r backend/requirements.txt --quiet

echo "[2/4] Checking frontend dependencies..."
if [ ! -d "frontend/node_modules" ]; then
    echo "Node modules not found. Running npm install..."
    (cd frontend && npm install --no-audit --no-fund --quiet)
fi

echo "[3/4] Starting FastAPI Backend on port 8000..."
(cd backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload) &
BACKEND_PID=$!

echo "[4/4] Starting Vite Frontend on port 3000..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

# Trap Ctrl+C to kill background processes
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT

echo "Waiting for services to start..."
sleep 10

URL="http://localhost:3000"
echo ""
echo "GridSight AI Platform is now running!"
echo "- Backend: http://localhost:8000"
echo "- Frontend: $URL"
echo ""

if command -v xdg-open > /dev/null; then
  xdg-open $URL
elif command -v open > /dev/null; then
  open $URL
else
  echo "Please open $URL manually."
fi

echo "Press Ctrl+C to stop the services."
wait
