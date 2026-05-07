@echo off
echo ==========================================
echo GridSight Prototype Launcher (Windows)
echo ==========================================

echo [1/6] Generating Synthetic Data...
python generate_data.py

echo [2/6] Validating and Cleaning Data...
python validate_and_load.py

echo [3/6] Training Forecasting Models (Prophet)...
python forecast_meters.py

echo [4/6] Running Anomaly Detection Pipeline...
python fusion_engine.py

echo [5/6] Running Performance Evaluation...
python evaluate.py

echo [6/6] Launching Unified Dashboard...
echo GridSight is running at http://localhost:8501
streamlit run app.py
