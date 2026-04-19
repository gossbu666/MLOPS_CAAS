"""
CAAS — FastAPI Inference Server
Serves PM2.5 forecasts (t+1, t+3, t+7) and hazard alerts.

Endpoints:
  GET  /health                  — liveness check
  GET  /forecast                — latest cached forecasts (t+1/3/7)
  POST /predict                 — on-demand prediction from raw features
  GET  /history?days=30         — recent PM2.5 history
  GET  /model/info              — current champion model metadata

Usage (local):
  uvicorn app:app --reload --port 8000

Usage (production on EC2):
  uvicorn app:app --host 0.0.0.0 --port 8000
"""

import os
import json
import glob
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import xgboost as xgb
import lightgbm as lgb

# ── Paths ──────────────────────────────────────────────────
BASE        = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(BASE)
DATA_DIR    = os.path.join(SCRIPTS_DIR, "..", "03_Data")
MODELS_DIR  = os.path.join(DATA_DIR, "models")
RESULTS_DIR = os.path.join(DATA_DIR, "results")
FEATURES    = os.path.join(DATA_DIR, "processed", "features.csv")
PM25_CSV    = os.path.join(DATA_DIR, "processed", "pm25_consolidated.csv")

ALERT_THRESHOLD = 50.0

# ── App setup ──────────────────────────────────────────────
app = FastAPI(
    title="CAAS — ChiangMai Air Quality Alert System",
    description="PM2.5 forecasting API: t+1, t+3, t+7 horizons with hazard alerts",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load models at startup ─────────────────────────────────
CHAMPION_NAME = "LightGBM"

models = {}              # champion: LightGBM Boosters  {"t1": Booster, ...}
xgb_models = {}          # fallback: XGBoost regressors for A/B comparison
model_metadata = {}      # populated from lightgbm_summary.json + xgboost_summary.json

@app.on_event("startup")
def load_models():
    # LightGBM — champion (tuned via Optuna, SP7)
    for horizon in ["t1", "t3", "t7"]:
        p = os.path.join(MODELS_DIR, f"lightgbm_{horizon}.txt")
        if os.path.exists(p):
            models[horizon] = lgb.Booster(model_file=p)
            print(f"✅  Loaded LightGBM champion: {horizon}")
        else:
            print(f"⚠️  LightGBM model not found: {p}")

    # XGBoost — available for A/B comparison via ?model=xgboost
    for horizon in ["t1", "t3", "t7"]:
        p = os.path.join(MODELS_DIR, f"xgboost_{horizon}.json")
        if os.path.exists(p):
            m = xgb.XGBRegressor()
            m.load_model(p)
            xgb_models[horizon] = m
            print(f"✅  Loaded XGBoost fallback: {horizon}")

    # Summaries
    for name in ("lightgbm", "xgboost"):
        sp = os.path.join(RESULTS_DIR, f"{name}_summary.json")
        if os.path.exists(sp):
            with open(sp) as f:
                model_metadata[name] = json.load(f)

# ── Helper: get latest features row ──────────────────────
def get_latest_features() -> Optional[pd.DataFrame]:
    if not os.path.exists(FEATURES):
        return None
    df = pd.read_csv(FEATURES, parse_dates=["date"], index_col="date")
    target_cols = [c for c in df.columns if c.startswith(("pm25_t", "alert_t"))]
    feature_cols = [c for c in df.columns if c not in target_cols]
    # Get the latest row that has lag features
    latest = df[feature_cols].dropna(subset=["pm25_lag1"]).tail(1)
    return latest

def _feature_names(model, kind: str) -> list:
    if kind == "lightgbm":
        return list(model.feature_name())
    return list(model.get_booster().feature_names)


def predict_all_horizons(feature_row: pd.DataFrame, model_kind: str = "lightgbm") -> dict:
    """Run all loaded models of the chosen kind on a feature row.
    model_kind ∈ {'lightgbm' (champion), 'xgboost' (fallback)}."""
    source = models if model_kind == "lightgbm" else xgb_models
    results = {}
    feature_row = feature_row.copy()

    # Median fill for any NaN features
    medians = None
    if os.path.exists(FEATURES):
        df_all = pd.read_csv(FEATURES, parse_dates=["date"], index_col="date")
        target_cols = [c for c in df_all.columns if c.startswith(("pm25_t", "alert_t"))]
        feature_cols = [c for c in df_all.columns if c not in target_cols]
        medians = df_all[feature_cols].median()
        feature_row = feature_row.fillna(medians)

    for horizon, model in source.items():
        model_input = feature_row.copy()
        expected_features = _feature_names(model, model_kind)

        # Align input columns to the exact feature names/order used in training.
        if expected_features:
            for col in expected_features:
                if col not in model_input.columns:
                    if medians is not None and col in medians.index:
                        model_input[col] = medians[col]
                    else:
                        model_input[col] = 0.0
            model_input = model_input[expected_features]

        pred = float(np.clip(model.predict(model_input)[0], 0, None))
        days = {"t1": 1, "t3": 3, "t7": 7}[horizon]
        results[horizon] = {
            "horizon_days": days,
            "pm25_forecast": round(pred, 1),
            "alert": pred > ALERT_THRESHOLD,
            "alert_level": get_alert_level(pred),
            "model": model_kind,
        }
    return results

def get_alert_level(pm25: float) -> str:
    if pm25 <= 15:   return "Good"
    if pm25 <= 25:   return "Moderate"
    if pm25 <= 37.5: return "Unhealthy for Sensitive Groups"
    if pm25 <= 50:   return "Unhealthy"
    if pm25 <= 75:   return "Very Unhealthy"
    return "Hazardous"

# ── Endpoints ──────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "champion": CHAMPION_NAME,
        "champion_horizons_loaded": list(models.keys()),
        "xgboost_horizons_loaded":  list(xgb_models.keys()),
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/forecast")
def get_forecast(model: str = "lightgbm"):
    """
    Returns the latest PM2.5 forecast for t+1, t+3, t+7 using the most
    recent data in features.csv. Defaults to LightGBM (champion); pass
    ?model=xgboost to get the XGBoost fallback for A/B comparison.
    """
    if model not in ("lightgbm", "xgboost"):
        raise HTTPException(400, f"model must be 'lightgbm' or 'xgboost', got {model!r}")

    source = models if model == "lightgbm" else xgb_models
    if not source:
        raise HTTPException(503, f"No {model} models loaded.")

    latest = get_latest_features()
    if latest is None:
        raise HTTPException(503, "Feature file not found. Run build_features.py first.")

    forecast_date = latest.index[-1]
    predictions = predict_all_horizons(latest, model_kind=model)

    return {
        "station":       "Chiang Mai (35T / 36T)",
        "as_of_date":    str(forecast_date.date()),
        "model":         model,
        "forecasts":     predictions,
        "generated_at":  datetime.now().isoformat(),
    }

@app.get("/history")
def get_history(days: int = 30):
    """Returns recent PM2.5 history for charting on the dashboard."""
    if not os.path.exists(PM25_CSV):
        raise HTTPException(503, "PM2.5 data file not found.")
    df = pd.read_csv(PM25_CSV, parse_dates=["date"])
    df = df[["date", "pm25"]].dropna().sort_values("date").tail(days)
    return {
        "station": "Chiang Mai",
        "days":    days,
        "data": [
            {
                "date":  str(row["date"].date()),
                "pm25":  row["pm25"],
                "alert": row["pm25"] > ALERT_THRESHOLD,
                "level": get_alert_level(row["pm25"]),
            }
            for _, row in df.iterrows()
        ],
    }

@app.get("/model/info")
def get_model_info():
    """Returns champion metadata + fallback model info."""
    return {
        "champion_model":    CHAMPION_NAME,
        "champion_metrics":  model_metadata.get("lightgbm", {}),
        "fallback_model":    "XGBoost",
        "fallback_metrics":  model_metadata.get("xgboost", {}),
        "champion_horizons": list(models.keys()),
        "fallback_horizons": list(xgb_models.keys()),
    }

class PredictRequest(BaseModel):
    """Raw feature dict for on-demand prediction."""
    pm25_lag1:  float
    pm25_lag3:  float
    pm25_lag7:  float
    pm25_lag14: float = 0.0
    pm25_lag30: float = 0.0
    pm25_roll3_mean:  float = 0.0
    pm25_roll7_mean:  float = 0.0
    pm25_roll14_mean: float = 0.0
    pm25_roll30_mean: float = 0.0
    pm25_roll7_std:   float = 0.0
    pm25_roll14_std:  float = 0.0
    month:          int   = 0
    week:           int   = 0
    day_of_year:    int   = 0
    sin_month:      float = 0.0
    cos_month:      float = 0.0
    sin_doy:        float = 0.0
    cos_doy:        float = 0.0
    is_haze_season: int   = 0

@app.post("/predict")
def predict(req: PredictRequest, model: str = "lightgbm"):
    """On-demand prediction from manually supplied feature values.
    Defaults to LightGBM champion; pass ?model=xgboost for fallback."""
    if model not in ("lightgbm", "xgboost"):
        raise HTTPException(400, f"model must be 'lightgbm' or 'xgboost', got {model!r}")

    source = models if model == "lightgbm" else xgb_models
    if not source:
        raise HTTPException(503, f"No {model} models loaded.")

    row = pd.DataFrame([req.dict()])
    # Pad missing feature columns with 0
    if os.path.exists(FEATURES):
        df_all = pd.read_csv(FEATURES, parse_dates=["date"], index_col="date")
        target_cols = [c for c in df_all.columns if c.startswith(("pm25_t","alert_t"))]
        feature_cols = [c for c in df_all.columns if c not in target_cols]
        for col in feature_cols:
            if col not in row.columns:
                row[col] = 0.0
        row = row[feature_cols]

    predictions = predict_all_horizons(row, model_kind=model)
    return {"input_features": req.dict(), "forecasts": predictions, "model": model}
