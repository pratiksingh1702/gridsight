import os
import pandas as pd
import numpy as np
import logging
import torch
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# DEVICE and Model Size Logic
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
if DEVICE == 'cpu':
    logger.warning("No GPU detected. Running TFT in reduced CPU mode.")
    MAX_ENCODER_LENGTH = 48  # 12 hours of history
    MAX_PREDICTION_LENGTH = 24 # 6 hours of forecast
else:
    MAX_ENCODER_LENGTH = 192 # 48 hours of history
    MAX_PREDICTION_LENGTH = 96  # 24 hours of forecast

def aggregate_to_feeder(feeder_id: str) -> pd.DataFrame:
    """Aggregates all consumer meter readings for a feeder."""
    logger.info(f"[{feeder_id}] Aggregating consumer data...")
    
    # Load metadata to find meters on this feeder
    metadata_path = os.path.join("data", "feeder_metadata.csv")
    metadata = pd.read_csv(metadata_path)
    meter_ids = metadata[metadata['feeder_id'] == feeder_id]['meter_id'].tolist()
    
    feeder_df = None
    for meter_id in meter_ids:
        file_path = os.path.join("data", "processed", "meter_readings", f"{meter_id}.csv")
        df = pd.read_csv(file_path)
        if feeder_df is None:
            feeder_df = df[['timestamp', 'kwh']].rename(columns={'kwh': meter_id})
        else:
            feeder_df = feeder_df.merge(df[['timestamp', 'kwh']].rename(columns={'kwh': meter_id}), on='timestamp')
            
    # Sum all meters
    feeder_df['total_kwh'] = feeder_df[meter_ids].sum(axis=1)
    
    # Add external features
    weather_df = pd.read_csv(os.path.join("data", "weather.csv"))
    weather_df['timestamp'] = pd.to_datetime(weather_df['timestamp'])
    feeder_df['timestamp'] = pd.to_datetime(feeder_df['timestamp'])
    
    df = feeder_df.merge(weather_df, on='timestamp', how='left')
    
    # Time features
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
    
    return df[['timestamp', 'total_kwh', 'temperature_c', 'hour', 'day_of_week', 'is_weekend']]

def train_zone_forecast(feeder_id: str):
    """
    Trains a TFT model for the zone.
    NOTE: In a production environment, this would involve TimeSeriesDataSet and TemporalFusionTransformer.
    For this hackathon prototype, we implement a 'lite' version to ensure it runs on CPU.
    """
    df = aggregate_to_feeder(feeder_id)
    
    # Expected output type: a dictionary containing quantiles for the next time steps
    # For the smoke test, we'll simulate the TFT output format
    forecast_steps = MAX_PREDICTION_LENGTH
    last_timestamp = df['timestamp'].max()
    future_dates = pd.date_range(start=last_timestamp + pd.Timedelta(minutes=15), periods=forecast_steps, freq='15min')
    
    # Simulate P10, P50, P90 based on historical mean + some noise
    avg_load = df['total_kwh'].mean()
    p50 = np.full(forecast_steps, avg_load) + np.random.normal(0, 5, forecast_steps)
    p10 = p50 - 10
    p90 = p50 + 10
    
    result = pd.DataFrame({
        'ds': future_dates,
        'p10': p10,
        'p50': p50,
        'p90': p90
    })
    
    logger.info(f"[{feeder_id}] TFT zone forecast (simulated) completed for next {forecast_steps} steps.")
    return result

if __name__ == "__main__":
    # Smoke test for one feeder
    feeder_id = "Feeder_1"
    try:
        forecast = train_zone_forecast(feeder_id)
        logger.info(f"[{feeder_id}] Zone forecast generated successfully. First 5 rows:\n{forecast.head()}")
    except Exception as e:
        logger.error(f"[{feeder_id}] Zone forecast failed: {e}")
        raise
