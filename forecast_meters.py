import os
import pandas as pd
import numpy as np
import logging
from prophet import Prophet
import joblib
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_bangalore_holidays():
    """
    Returns a dataframe of Bangalore holidays for Prophet.
    Holidays: Diwali, Ugadi, Eid, Christmas, Republic Day, Independence Day,
    Kannada Rajyotsava, Ganesh Chaturthi, Dasara.
    """
    holidays = pd.DataFrame({
      'holiday': 'bangalore_holiday',
      'ds': pd.to_datetime([
          '2026-01-26', # Republic Day
          '2026-03-20', # Ugadi (approx)
          '2026-03-31', # Eid al-Fitr (approx)
          '2026-08-15', # Independence Day
          '2026-09-17', # Ganesh Chaturthi
          '2026-10-20', # Dasara
          '2026-11-01', # Kannada Rajyotsava
          '2026-11-08', # Diwali (approx)
          '2026-12-25', # Christmas
      ]),
      'lower_window': 0,
      'upper_window': 1,
    })
    return holidays

def train_and_forecast(meter_id: str) -> pd.DataFrame:
    """
    Trains a Prophet model for a specific meter and forecasts next 24 hours.
    
    Production weather source note (Suggestion 5):
    IMD Open Data (mausam.imd.gov.in) or Open-Meteo API (api.open-meteo.com).
    Resample hourly to 15-min via linear interpolation. 
    Only aggregate area-level weather is used; no consumer data leaves BESCOM.
    """
    logger.info(f"[{meter_id}] Training Prophet model...")
    
    # Load history
    if config.USE_DB:
        # Placeholder for DB query
        logger.info(f"[{meter_id}] Querying DB...")
        # df = pd.read_sql(...)
        df = pd.DataFrame() 
    else:
        file_path = os.path.join("data", "processed", "meter_readings", f"{meter_id}.csv")
        df = pd.read_csv(file_path)
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Load weather for regressors
    weather_path = os.path.join("data", "weather.csv")
    weather_df = pd.read_csv(weather_path)
    weather_df['timestamp'] = pd.to_datetime(weather_df['timestamp'])
    
    # Merge weather with consumption
    train_df = df.merge(weather_df, on='timestamp', how='left')
    
    # Prophet expects 'ds' and 'y'
    prophet_df = train_df[['timestamp', 'kwh', 'temperature_c']].rename(columns={'timestamp': 'ds', 'kwh': 'y'})
    
    # Initialize and train
    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=False,
        holidays=get_bangalore_holidays()
    )
    model.add_regressor('temperature_c')
    model.fit(prophet_df)
    
    # Save model
    model_dir = os.path.join("models", "prophet")
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(model, os.path.join(model_dir, f"{meter_id}.pkl"))
    
    # Forecast next 24h (96 steps of 15min)
    future = model.make_future_dataframe(periods=96, freq='15min')
    
    # We need future temperature. In production, this comes from an API.
    # For prototype, we'll use a simple forecast (mean + trend) or dummy values.
    # Here, we'll just extend the last known temperature with some daily pattern.
    last_temp = prophet_df['temperature_c'].iloc[-1]
    future_temps = np.full(len(future) - len(prophet_df), last_temp) # Dummy
    
    # To be more realistic, let's just use the weather_df if it has future dates, 
    # but generate_data only generated up to 'today'.
    # For now, append the dummy temps to the original temps
    all_temps = np.concatenate([prophet_df['temperature_c'].values, future_temps])
    future['temperature_c'] = all_temps
    
    forecast = model.predict(future)
    
    # Return next 24h only
    result = forecast.tail(96)[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
    return result

if __name__ == "__main__":
    # Smoke test for one meter
    meter_id = "meter_000"
    try:
        forecast = train_and_forecast(meter_id)
        logger.info(f"[{meter_id}] Forecast generated successfully. First 5 rows:\n{forecast.head()}")
    except Exception as e:
        logger.error(f"[{meter_id}] Forecast failed: {e}")
        raise
