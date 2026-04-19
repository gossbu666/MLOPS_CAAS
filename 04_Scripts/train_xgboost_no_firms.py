"""
CAAS — Scenario D: FIRMS Ablation Study
Trains XGBoost WITHOUT NASA FIRMS fire hotspot features (39 features instead of 45).
Compare results against full 45-feature model to quantify FIRMS contribution.

FIRMS features removed (6 total):
  hotspot_50km, hotspot_100km, mean_frp_50km,
  hotspot_7d_roll, hotspot_14d_roll, fire_flag

Usage:
    python 04_Scripts/train_xgboost_no_firms.py

Output:
    03_Data/results/ablation_no_firms_t1/t3/t7_test_predictions.csv
    03_Data/results/ablation_summary.json
"""

import os
import json
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
import xgboost as xgb
import mlflow
import warnings
warnings.filterwarnings("ignore")

BASE        = os.path.dirname(os.path.abspath(__file__))
FEATURES    = os.path.join(BASE, "..", "03_Data", "processed", "features.csv")
RESULTS_DIR = os.path.join(BASE, "..", "03_Data", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

TRAIN_END = "2022-12-31"
VAL_END   = "2023-12-31"
ALERT_THRESHOLD = 50.0

# FIRMS features to DROP for ablation
FIRMS_FEATURES = [
    "hotspot_50km", "hotspot_100km", "mean_frp_50km",
    "hotspot_7d_roll", "hotspot_14d_roll", "fire_flag",
]

HORIZONS = {
    "t1": ("pm25_t1", "alert_t1"),
    "t3": ("pm25_t3", "alert_t3"),
    "t7": ("pm25_t7", "alert_t7"),
}

XGB_PARAMS = {
    "n_estimators":       500,
    "learning_rate":      0.05,
    "max_depth":          6,
    "min_child_weight":   5,
    "colsample_bytree":   0.8,
    "reg_alpha":          0.1,
    "reg_lambda":         1.0,
    "random_state":       42,
    "n_jobs":             -1,
    "early_stopping_rounds": 30,
}

# Load full model results for comparison
full_summary_path = os.path.join(RESULTS_DIR, "xgboost_summary.json")
with open(full_summary_path) as f:
    full_summary = json.load(f)

print("📂  Loading features...")
df = pd.read_csv(FEATURES, parse_dates=["date"], index_col="date")
print(f"   Shape: {df.shape}")

target_cols  = [c for c in df.columns if c.startswith(("pm25_t", "alert_t"))]
feature_cols = [c for c in df.columns if c not in target_cols]

# Drop FIRMS features
firms_present = [f for f in FIRMS_FEATURES if f in feature_cols]
feature_cols_no_firms = [c for c in feature_cols if c not in firms_present]
print(f"   Full features : {len(feature_cols)}")
print(f"   FIRMS dropped : {firms_present}")
print(f"   Ablation feat : {len(feature_cols_no_firms)}")

# Impute
df_train_raw  = df[df.index <= TRAIN_END]
train_medians = df_train_raw[feature_cols_no_firms].median()
df[feature_cols_no_firms] = df[feature_cols_no_firms].fillna(train_medians)

mlflow.set_tracking_uri(os.path.join(BASE, "..", "mlruns"))
mlflow.set_experiment("CAAS-Ablation-NoFIRMS")

ablation_results = {}

for horizon, (reg_target, cls_target) in HORIZONS.items():
    print(f"\n{'='*55}")
    print(f"🎯  Scenario D — Horizon {horizon.upper()} (no FIRMS)")

    df_h  = df[[*feature_cols_no_firms, reg_target, cls_target]].dropna(subset=[reg_target])
    df_tr = df_h[df_h.index <= TRAIN_END]
    df_vl = df_h[(df_h.index > TRAIN_END) & (df_h.index <= VAL_END)]
    df_te = df_h[df_h.index > VAL_END]

    X_tr, y_tr       = df_tr[feature_cols_no_firms], df_tr[reg_target].values
    X_vl, y_vl       = df_vl[feature_cols_no_firms], df_vl[reg_target].values
    X_te, y_te       = df_te[feature_cols_no_firms], df_te[reg_target].values
    y_cls_te          = df_te[cls_target].astype(int).values

    with mlflow.start_run(run_name=f"Ablation-NoFIRMS-{horizon}"):
        model = xgb.XGBRegressor(**XGB_PARAMS)
        model.fit(
            X_tr, y_tr,
            eval_set=[(X_vl, y_vl)],
            verbose=False,
        )

        pred_te = np.clip(model.predict(X_te), 0, None)

        mae  = mean_absolute_error(y_te, pred_te)
        rmse = np.sqrt(mean_squared_error(y_te, pred_te))
        r2   = r2_score(y_te, pred_te)

        pred_cls = (pred_te > ALERT_THRESHOLD).astype(int)
        precision = precision_score(y_cls_te, pred_cls, zero_division=0)
        recall    = recall_score(y_cls_te, pred_cls, zero_division=0)
        f1        = f1_score(y_cls_te, pred_cls, zero_division=0)
        try:
            auroc = roc_auc_score(y_cls_te, pred_te)
        except Exception:
            auroc = float("nan")

        mlflow.log_params({"horizon": horizon, "n_features": len(feature_cols_no_firms),
                           "firms_dropped": len(firms_present)})
        mlflow.log_metrics({"test_mae": mae, "test_rmse": rmse, "test_r2": r2,
                            "test_alert_f1": f1, "test_alert_recall": recall,
                            "test_alert_auroc": auroc})

        # Full model metrics for comparison
        # Supports both current nested format and legacy flat keys.
        full_horizon_metrics = full_summary.get(horizon, {})
        if "test" in full_horizon_metrics and isinstance(full_horizon_metrics["test"], dict):
            full_mae = full_horizon_metrics["test"].get("mae")
            full_rmse = full_horizon_metrics["test"].get("rmse")
        else:
            full_mae = full_horizon_metrics.get("test_mae")
            full_rmse = full_horizon_metrics.get("test_rmse")

        if full_mae is None or full_rmse is None:
            raise KeyError(
                f"Missing full model test metrics for horizon '{horizon}' in {full_summary_path}. "
                "Expected either ['<horizon>']['test']['mae'/'rmse'] or legacy ['<horizon>']['test_mae'/'test_rmse']."
            )

        mae_delta = (mae - full_mae) / full_mae * 100  # positive = worse

        print(f"   No-FIRMS  MAE={mae:.2f}  RMSE={rmse:.2f}  R²={r2:.3f}")
        print(f"   Full-45   MAE={full_mae:.2f}  RMSE={full_rmse:.2f}")
        print(f"   FIRMS lift: {'-' if mae_delta < 0 else '+'}{abs(mae_delta):.1f}% MAE change")

        ablation_results[horizon] = {
            "no_firms_mae":  round(mae,  3),
            "no_firms_rmse": round(rmse, 3),
            "no_firms_r2":   round(r2,   3),
            "no_firms_recall": round(recall, 3),
            "no_firms_f1":   round(f1,   3),
            "no_firms_auroc": round(auroc, 3),
            "full_mae":      round(full_mae,  3),
            "full_rmse":     round(full_rmse, 3),
            "mae_pct_change": round(mae_delta, 2),
        }

        # Save predictions
        out_df = pd.DataFrame({
            "date":      df_te.index,
            "actual":    y_te,
            "predicted": pred_te,
        })
        out_path = os.path.join(RESULTS_DIR, f"ablation_no_firms_{horizon}_test_predictions.csv")
        out_df.to_csv(out_path, index=False)

# Save ablation summary
summary_path = os.path.join(RESULTS_DIR, "ablation_summary.json")
with open(summary_path, "w") as f:
    json.dump(ablation_results, f, indent=2)
print(f"\n✅  Ablation summary saved: {summary_path}")
print("\n🎉  Scenario D complete — run generate_ablation_plot.py next")
