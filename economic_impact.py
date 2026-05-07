import os
import logging
import pandas as pd
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _load_meter_meta(meter_id: str) -> dict:
    meta_path = os.path.join("data", "feeder_metadata.csv")
    if not os.path.exists(meta_path):
        return {}
    meta = pd.read_csv(meta_path)
    row = meta[meta['meter_id'] == meter_id]
    if row.empty:
        return {}
    return row.iloc[0].to_dict()


def _tariff_for_meter(meta: dict) -> float:
    meter_type = str(meta.get('type', 'residential')).lower()
    if meter_type == 'commercial':
        return config.TARIFF_COMMERCIAL_PER_KWH
    return config.TARIFF_RESIDENTIAL_PER_KWH


def compute_economic_impact(meter_id: str, residual_df: pd.DataFrame | None, p_theft: float) -> dict:
    loss_kwh = 0.0
    if residual_df is not None and not residual_df.empty:
        negative_residual = residual_df[residual_df['residual_kwh'] < 0]['residual_kwh']
        loss_kwh = float(abs(negative_residual.sum()))

    meta = _load_meter_meta(meter_id)
    tariff = _tariff_for_meter(meta)
    loss_value = loss_kwh * tariff

    projected_loss_30d = (loss_value / max(1, config.RESIDUAL_FORECAST_DAYS)) * config.LOSS_PROJECTION_DAYS
    expected_value = p_theft * projected_loss_30d
    expected_recovery = expected_value * config.RECOVERY_RATE
    roi = expected_recovery / max(1.0, config.INSPECTION_COST)

    loss_scale = max(1.0, config.LOSS_SCALE_FOR_PRIORITY)
    expected_scale = max(1.0, loss_scale)
    priority_score = 100.0 * (
        0.4 * min(1.0, expected_value / expected_scale) +
        0.4 * min(1.0, roi / config.ROI_TARGET) +
        0.2 * min(1.0, p_theft)
    )

    return {
        'loss_kwh': loss_kwh,
        'loss_value': loss_value,
        'projected_loss_30d_value': projected_loss_30d,
        'expected_value': expected_value,
        'roi': roi,
        'priority_score': min(100.0, priority_score),
        'tariff_per_kwh': tariff
    }
