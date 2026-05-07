@echo off
setlocal
echo ==========================================
echo GridSight 3D Platform Launcher (Windows)
echo ==========================================

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python to continue.
    pause
    exit /b 1
)

echo [1/4] Installing backend dependencies...
python -m pip install -r backend/requirements.txt --quiet

echo [2/4] Checking frontend dependencies...
if not exist "frontend\node_modules\" (
    echo Node modules not found. Running npm install...
    cd frontend && npm install --no-audit --no-fund --quiet && cd ..
)

echo [3/4] Starting FastAPI Backend on port 8000...
start "GridSight-Backend" cmd /k "cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo [4/4] Starting Vite Frontend on port 3000...
start "GridSight-Frontend" cmd /k "cd frontend && npm run dev"

:: Wait for services to warm up
echo Waiting for services to start...
timeout /t 10 /nobreak > nul

echo.
echo Opening GridSight Dashboard...
start http://localhost:3000

echo.
echo GridSight AI Platform is now running!
echo - Backend: http://localhost:8000
echo - Frontend: http://localhost:3000
echo.
echo Close the terminal windows to stop the services.
pause
