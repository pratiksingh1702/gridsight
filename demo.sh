#!/bin/bash
echo "=========================================="
echo "GridSight Prototype Launcher (Linux/WSL)"
echo "=========================================="

echo "[1/6] Generating Synthetic Data..."
python3 generate_data.py

echo "[2/6] Validating and Cleaning Data..."
python3 validate_and_load.py

echo "[3/6] Training Forecasting Models (Prophet)..."
python3 forecast_meters.py

echo "[4/6] Running Anomaly Detection Pipeline..."
python3 fusion_engine.py

echo "[5/6] Running Performance Evaluation..."
python3 evaluate.py

echo "[6/6] Launching Unified Dashboard..."
echo "GridSight is running at http://localhost:8501"
streamlit run app.py
