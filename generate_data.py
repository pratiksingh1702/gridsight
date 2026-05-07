import os
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from faker import Faker
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

fake = Faker()
Faker.seed(42)
np.random.seed(42)

def generate_weather(days: int, freq: str) -> pd.DataFrame:
    """Generates synthetic weather data with daily temperature fluctuations."""
    logger.info("Generating weather data...")
    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    timestamps = pd.date_range(start=start_date, periods=days * (24 * 4 if freq == "15min" else 24), freq=freq)
    
    # Base temperature: sinusoidal annual/seasonal (simplified to daily)
    # Peak at 14:00, dip at 04:00. Average around 28C.
    hour = (timestamps.hour + timestamps.minute / 60).values
    temp = 25 + 10 * np.sin(2 * np.pi * (hour - 8) / 24) + np.random.normal(0, 0.5, len(timestamps))
    
    # Add heatwave days (temp > 35C)
    heatwave_indices = np.random.choice(range(len(timestamps)), size=int(len(timestamps) * 0.05))
    temp[heatwave_indices] += 8

    humidity = 60 - 20 * np.sin(2 * np.pi * (hour - 8) / 24) + np.random.normal(0, 2, len(timestamps))
    
    df = pd.DataFrame({
        "timestamp": timestamps,
        "temperature_c": temp,
        "humidity_pct": humidity
    })
    return df

def generate_meter_data(meter_id: str, meter_type: str, weather_df: pd.DataFrame, theft_type: str = None, injection_date: datetime = None) -> pd.DataFrame:
    """Generates 15-min load profile for a single meter."""
    df = weather_df.copy()
    hour = df['timestamp'].dt.hour + df['timestamp'].dt.minute / 60
    day_of_week = df['timestamp'].dt.dayofweek # 0=Monday
    
    # Base load logic
    if meter_type == "residential":
        base_kwh = np.random.uniform(0.3, 0.8)
        # Peak 18:00-20:00, Dip 03:00-05:00
        diurnal = 0.5 * (1 + np.sin(2 * np.pi * (hour - 12) / 24)) 
        # Shift peak to evening
        diurnal = np.roll(diurnal, int((19-12)*4)) 
    else: # commercial
        base_kwh = np.random.uniform(1.0, 3.0)
        # Peak during day 09:00-18:00
        diurnal = np.where((hour >= 9) & (hour <= 18), 1.0, 0.2)
    
    # Weekly seasonality: weekdays higher than weekends
    weekly = np.where(day_of_week < 5, 1.0, 0.7)
    
    # Temperature sensitivity
    temp_factor = np.where(df['temperature_c'] > 35, 1.20, 1.0)
    
    # Combine
    kwh = base_kwh * diurnal * weekly * temp_factor
    kwh += np.random.normal(0, 0.08 * kwh) # Noise
    kwh = np.maximum(kwh, 0.01) # Minimum standby
    
    # Voltage generation (Suggestion 2)
    voltage = 230 + np.random.normal(0, 2, len(df))
    
    clean_kwh = kwh.copy()
    
    # Theft Injection (after day 45)
    if theft_type and injection_date:
        mask = df['timestamp'] >= injection_date
        
        if theft_type == "bypass":
            # sudden 70-85% drop
            reduction = np.random.uniform(0.15, 0.30)
            kwh[mask] *= reduction
            voltage[mask] -= np.random.uniform(8, 15) # Voltage dip on theft days
        elif theft_type == "flatline":
            # frozen at last value
            idx = df[mask].index[0]
            last_val = kwh[idx-1]
            kwh[mask] = last_val
        elif theft_type == "night_zero":
            # zero between 22:00-06:00
            night_mask = mask & ((df['timestamp'].dt.hour >= 22) | (df['timestamp'].dt.hour < 6))
            kwh[night_mask] = 0.005 # Near zero
        elif theft_type == "periodic_dip":
            # 80% drop for 2 days every 15 days
            days_since_start = (df['timestamp'] - df['timestamp'].min()).dt.days
            dip_mask = mask & ((days_since_start % 15 == 0) | (days_since_start % 15 == 1))
            kwh[dip_mask] *= 0.2
        elif theft_type == "gradual_decline":
            # drops 5% per week for 6 weeks
            weeks_since_injection = (df[mask]['timestamp'] - injection_date).dt.days // 7
            decline_factors = np.maximum(1.0 - (weeks_since_injection * 0.05), 0.5)
            # Apply decline factors carefully to the mask
            kwh_mask = kwh[mask]
            # Since weeks_since_injection is an array of the same length as kwh_mask
            kwh[mask] = kwh_mask * decline_factors

    df['kwh'] = kwh
    df['voltage'] = voltage
    df['status'] = "NORMAL"
    return df[['timestamp', 'kwh', 'voltage', 'status']], clean_kwh

def run_data_generation():
    """Main function to generate all synthetic data files."""
    data_dir = "data"
    meter_dir = os.path.join(data_dir, "meter_readings")
    feeder_dir = os.path.join(data_dir, "feeder_head_readings")
    
    os.makedirs(meter_dir, exist_ok=True)
    os.makedirs(feeder_dir, exist_ok=True)
    
    weather_df = generate_weather(config.DAYS, config.FREQ)
    weather_df.to_csv(os.path.join(data_dir, "weather.csv"), index=False)
    
    # 1. Generate Metadata and assign feeders
    num_feeders = 5
    feeders = [f"Feeder_{i+1}" for i in range(num_feeders)]
    meters_metadata = []
    
    # Theft assignment
    theft_indices = np.random.choice(range(config.NUM_METERS), size=config.THEFT_METERS, replace=False)
    theft_types = ["bypass"] * 3 + ["flatline"] * 2 + ["night_zero"] * 2 + ["periodic_dip"] * 2 + ["gradual_decline"] * 1
    np.random.shuffle(theft_types)
    
    injection_date = weather_df['timestamp'].min() + timedelta(days=45)
    theft_ground_truth = []

    feeder_consumers = {f: [] for f in feeders}
    
    feeder_clean_kwh = {f: None for f in feeders}
    
    logger.info(f"Generating data for {config.NUM_METERS} meters...")
    for i in range(config.NUM_METERS):
        meter_id = f"meter_{i:03d}"
        meter_type = "residential" if i < config.NUM_METERS * 0.8 else "commercial"
        feeder_id = feeders[i % num_feeders]
        feeder_consumers[feeder_id].append(meter_id)
        
        theft_type = None
        if i in theft_indices:
            theft_type = theft_types[list(theft_indices).index(i)]
            theft_ground_truth.append({
                "meter_id": meter_id,
                "theft_type": theft_type,
                "injection_date": injection_date.isoformat()
            })
        
        # Generate readings
        df, clean_kwh = generate_meter_data(meter_id, meter_type, weather_df, theft_type, injection_date)
        df.to_csv(os.path.join(meter_dir, f"{meter_id}.csv"), index=False)
        
        if feeder_clean_kwh[feeder_id] is None:
            feeder_clean_kwh[feeder_id] = clean_kwh
        else:
            feeder_clean_kwh[feeder_id] += clean_kwh
        
        # Metadata
        meters_metadata.append({
            "meter_id": meter_id,
            "feeder_id": feeder_id,
            "type": meter_type,
            "name": fake.name(),
            "address": fake.address().replace("\n", ", "),
            "latitude": 12.97 + np.random.normal(0, 0.05),
            "longitude": 77.59 + np.random.normal(0, 0.05)
        })

    pd.DataFrame(meters_metadata).to_csv(os.path.join(data_dir, "feeder_metadata.csv"), index=False)
    pd.DataFrame(theft_ground_truth).to_csv(os.path.join(data_dir, "theft_ground_truth.csv"), index=False)
    
    # 2. Generate Feeder Head Readings (Suggestion 1)
    logger.info("Generating feeder head readings...")
    for feeder_id, consumer_ids in feeder_consumers.items():
        # Feeder head kwh = sum(CLEAN) * (1 + tech_loss) + noise
        tech_loss = config.NORMAL_TECHNICAL_LOSS_PCT / 100.0
        clean_sum = feeder_clean_kwh[feeder_id]
        feeder_head_kwh = clean_sum * (1 + tech_loss) + np.random.normal(0, 0.005 * clean_sum)
        
        # simplified voltage (use average from metadata or just 230)
        feeder_head_df = pd.DataFrame({
            "timestamp": weather_df['timestamp'],
            "kwh": feeder_head_kwh,
            "voltage": 230.0 + np.random.normal(0, 1, len(weather_df)),
            "status": "NORMAL"
        })
        feeder_head_df.to_csv(os.path.join(feeder_dir, f"{feeder_id}_head.csv"), index=False)

    logger.info("Data generation complete.")

if __name__ == "__main__":
    run_data_generation()
