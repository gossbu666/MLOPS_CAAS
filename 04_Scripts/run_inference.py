"""
CAAS — Run Inference (Near-Real-Time Forecast)
Loads the champion XGBoost models, runs inference on the latest
feature row, and saves the forecast to results/latest_forecast.json.

Called by: .github/workflows/daily_pipeline.yml  step [3/4]
Runs every 3 hours — forecast_history.csv stores all runs with timestamps,
not just one per day. This lets the dashboard show how forecasts evolve
throughout the day as new data arrives.

Usage:
    python run_inference.py
"""

import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import xgboost as xgb

BKK = ZoneInfo("Asia/Bangkok")

# ── Paths ───────────────────────────────────────────────────
BASE        = os.path.dirname(os.path.abspath(__file__))
FEATURES    = os.path.join(BASE, "..", "03_Data", "processed", "features.csv")
MODELS_DIR  = os.path.join(BASE, "..", "03_Data", "models")
RESULTS_DIR = os.path.join(BASE, "..", "03_Data", "results")
HISTORY_CSV = os.path.join(RESULTS_DIR, "forecast_history.csv")

ALERT_THRESHOLD = 50.0
HORIZONS        = ["t1", "t3", "t7"]

os.makedirs(RESULTS_DIR, exist_ok=True)


def get_alert_level(pm25: float) -> str:
    if pm25 <= 15:   return "Good"
    if pm25 <= 25:   return "Moderate"
    if pm25 <= 37.5: return "Unhealthy for Sensitive Groups"
    if pm25 <= 50:   return "Unhealthy"
    if pm25 <= 75:   return "Very Unhealthy"
    return "Hazardous"


def main():
    print("📂  Loading feature matrix...")
    df = pd.read_csv(FEATURES, parse_dates=["date"], index_col="date")

    target_cols  = [c for c in df.columns if c.startswith(("pm25_t", "alert_t"))]
    feature_cols = [c for c in df.columns if c not in target_cols]

    # Most recent complete row (has pm25_lag1)
    df_feat = df[feature_cols]
    latest_row = df_feat.dropna(subset=["pm25_lag1"]).tail(1)

    if latest_row.empty:
        raise RuntimeError("No complete feature rows found. Run build_features.py first.")

    forecast_date = latest_row.index[-1]
    print(f"   Feature row date: {forecast_date.date()}")

    # Impute any remaining NaN with training medians
    df_train = df_feat[df.index <= "2022-12-31"]
    train_medians = df_train.median()
    latest_row = latest_row.fillna(train_medians).fillna(0)

    print("\n🤖  Running inference...")
    forecasts = {}

    for horizon in HORIZONS:
        model_path = os.path.join(MODELS_DIR, f"xgboost_{horizon}.json")
        if not os.path.exists(model_path):
            print(f"   ⚠️  Model not found: {model_path}")
            continue

        model = xgb.XGBRegressor()
        model.load_model(model_path)

        # Align feature order to what the model was trained on
        expected = model.get_booster().feature_names
        row_aligned = latest_row.copy()
        for col in expected:
            if col not in row_aligned.columns:
                row_aligned[col] = train_medians.get(col, 0.0)
        row_aligned = row_aligned[expected]

        pred = float(np.clip(model.predict(row_aligned)[0], 0, None))
        days = int(horizon[1])

        forecasts[horizon] = {
            "horizon_days":   days,
            "pm25_forecast":  round(pred, 2),
            "alert":          bool(pred > ALERT_THRESHOLD),
            "alert_level":    get_alert_level(pred),
        }

        print(f"   t+{days}: {pred:.1f} µg/m³  [{get_alert_level(pred)}]")

    now_utc = datetime.now(timezone.utc)
    now_bkk = now_utc.astimezone(BKK)

    # ── Compute data freshness (Thai timezone) ──────────────
    # PM2.5 dates in the CSV are Thai local dates. Compare against Thai today.
    pm25_csv = os.path.join(os.path.dirname(FEATURES), "pm25_consolidated.csv")
    data_age_days = None
    data_freshness_minutes = None
    latest_pm25_date = None
    if os.path.exists(pm25_csv):
        pm25_df = pd.read_csv(pm25_csv, parse_dates=["date"])
        if not pm25_df.empty:
            latest_pm25_date = pm25_df["date"].max()
            data_age_days = (now_bkk.date() - latest_pm25_date.date()).days
            latest_midnight_bkk = datetime.combine(
                latest_pm25_date.date(), datetime.min.time(), tzinfo=BKK
            )
            data_freshness_minutes = int((now_bkk - latest_midnight_bkk).total_seconds() / 60)

    # ── Save latest_forecast.json ────────────────────────────
    output = {
        "station":                "Chiang Mai (35T)",
        "forecast_for":           str(forecast_date.date()),
        "generated_at":           now_utc.isoformat().replace("+00:00", "Z"),
        "generated_at_local":     now_bkk.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "data_age_days":          data_age_days,
        "data_freshness_minutes": data_freshness_minutes,
        "latest_pm25_date":       str(latest_pm25_date.date()) if latest_pm25_date is not None else None,
        "forecasts":              forecasts,
    }

    out_path = os.path.join(RESULTS_DIR, "latest_forecast.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n✅  Forecast saved → {out_path}")
    if data_age_days is not None:
        print(f"   Data age: {data_age_days} day(s) "
              f"(latest PM2.5: {latest_pm25_date.date()}, now BKK: {now_bkk.date()})")

    # ── Append to forecast history CSV ───────────────────────
    # Store EVERY run (not just one per day) so the dashboard can show
    # how forecasts evolve through the day as new data arrives.
    history_row = {
        "date":        str(forecast_date.date()),
        "generated_at": now_utc.isoformat().replace("+00:00", "Z"),
    }
    for h, fc in forecasts.items():
        history_row[f"pm25_{h}"] = fc["pm25_forecast"]
        history_row[f"alert_{h}"] = int(fc["alert"])

    history_df = pd.DataFrame([history_row])
    if os.path.exists(HISTORY_CSV):
        existing = pd.read_csv(HISTORY_CSV)
        history_df = pd.concat([existing, history_df], ignore_index=True)

    history_df.to_csv(HISTORY_CSV, index=False)
    print(f"✅  History appended → {HISTORY_CSV}")


if __name__ == "__main__":
    main()
