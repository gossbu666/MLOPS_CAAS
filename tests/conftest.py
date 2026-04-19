"""
Shared pytest fixtures for CAAS test suite.
"""
import os
import pytest
import pandas as pd

# ── Project root (one level up from tests/) ────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FEATURES_CSV   = os.path.join(ROOT, "03_Data", "processed", "features.csv")
MODELS_DIR     = os.path.join(ROOT, "03_Data", "models")
RESULTS_DIR    = os.path.join(ROOT, "03_Data", "results")
SCRIPTS_DIR    = os.path.join(ROOT, "04_Scripts")

EXPECTED_FEATURES = [
    "pm25_lag1", "pm25_lag3", "pm25_lag7", "pm25_lag14", "pm25_lag30",
    "pm25_roll3_mean", "pm25_roll7_mean", "pm25_roll14_mean", "pm25_roll30_mean",
    "pm25_roll7_std", "pm25_roll14_std",
    "month", "week", "day_of_year",
    "sin_month", "cos_month", "sin_doy", "cos_doy", "is_haze_season",
    "temp_max", "temp_min", "temp_mean", "humidity_max", "humidity_min",
    "precipitation", "wind_speed", "pressure", "cloud_cover",
    "evapotranspiration", "wind_dir_sin", "wind_dir_cos",
    "hotspot_50km", "hotspot_100km", "mean_frp_50km",
    "hotspot_7d_roll", "hotspot_14d_roll", "fire_flag",
    "alert_lag1", "alert_lag3", "alert_lag7",
    "lag1_x_temp", "lag1_x_wind", "roll7_x_fire", "precip_flag", "humidity_wind",
]

EXPECTED_TARGETS = ["pm25_t1", "pm25_t3", "pm25_t7", "alert_t1", "alert_t3", "alert_t7"]
HORIZONS = ["t1", "t3", "t7"]


@pytest.fixture(scope="session")
def features_df():
    """Load features.csv once for the whole test session."""
    assert os.path.exists(FEATURES_CSV), f"features.csv not found at {FEATURES_CSV}"
    return pd.read_csv(FEATURES_CSV, parse_dates=["date"], index_col="date")


@pytest.fixture(scope="session")
def xgb_models():
    """Load all 3 XGBoost models once."""
    import xgboost as xgb
    models = {}
    for h in HORIZONS:
        path = os.path.join(MODELS_DIR, f"xgboost_{h}.json")
        assert os.path.exists(path), f"Model not found: {path}"
        m = xgb.XGBRegressor()
        m.load_model(path)
        models[h] = m
    return models
