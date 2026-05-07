import logging
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def classify_risk(predicted_peak_kw: float, rated_capacity_kw: float) -> str:
    """
    Classifies a transformer's peak risk based on predicted-to-rated ratio.
    Uses thresholds defined in config.py.
    """
    if rated_capacity_kw <= 0:
        logger.error("Rated capacity must be greater than zero.")
        raise ValueError("Rated capacity must be greater than zero.")
        
    ratio = predicted_peak_kw / rated_capacity_kw
    
    if ratio < config.RISK_ZONE_YELLOW:
        return "GREEN"
    elif ratio < config.RISK_ZONE_ORANGE:
        return "YELLOW"
    elif ratio < config.RISK_ZONE_RED:
        return "ORANGE"
    else:
        return "RED"

if __name__ == "__main__":
    # Smoke test
    tests = [
        (50, 100),  # 0.50 -> GREEN
        (75, 100),  # 0.75 -> YELLOW
        (90, 100),  # 0.90 -> ORANGE
        (100, 100)  # 1.00 -> RED
    ]
    
    for peak, cap in tests:
        zone = classify_risk(peak, cap)
        logger.info(f"Peak: {peak}kW, Capacity: {cap}kW -> Risk Zone: {zone}")
