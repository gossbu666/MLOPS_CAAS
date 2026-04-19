"""
CAAS — XGBoost Training Script (with MLflow)
Trains one XGBoost model per forecast horizon (t+1, t+3, t+7).
Uses strict chronological split: train 2011-2022, val 2023, test 2024-2025.

Usage:
    python train_xgboost.py

Requirements: features.csv must exist (run build_features.py first)
MLflow UI: mlflow ui  (then open http://localhost:5000)
"""

import os
import json
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
import xgboost as xgb
import mlflow
import mlflow.xgboost
import warnings
warnings.filterwarnings("ignore")

# ── Config ─────────────────────────────────────────────────
BASE        = os.path.dirname(os.path.abspath(__file__))
FEATURES    = os.path.join(BASE, "..", "03_Data", "processed", "features.csv")
MODELS_DIR  = os.path.join(BASE, "..", "03_Data", "models")
RESULTS_DIR = os.path.join(BASE, "..", "03_Data", "results")

TRAIN_END = "2022-12-31"
VAL_END   = "2023-12-31"
# Test = 2024-01-01 → end

HORIZONS = {
    "t1": ("pm25_t1", "alert_t1"),
    "t3": ("pm25_t3", "alert_t3"),
    "t7": ("pm25_t7", "alert_t7"),
}

ALERT_THRESHOLD = 50.0

# Base XGBoost hyperparameters (tuned on validation set for t+1 and t+3)
XGB_PARAMS_BASE = {
    "n_estimators":     500,
    "max_depth":        6,
    "learning_rate":    0.05,
    "subsample":        0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "reg_alpha":        0.1,
    "reg_lambda":       1.0,
    "random_state":     42,
    "n_jobs":           -1,
    "early_stopping_rounds": 30,
}

# t+7 gets its own params: shallower trees + more estimators + more regularisation
# Rationale: 7-day PM2.5 is harder to predict; deeper trees overfit the training period.
# Lower LR + more rounds + depth=4 gives the model more chances to generalise.
XGB_PARAMS_T7 = {
    "n_estimators":     1000,
    "max_depth":        4,
    "learning_rate":    0.03,
    "subsample":        0.8,
    "colsample_bytree": 0.7,
    "min_child_weight": 7,
    "reg_alpha":        0.3,
    "reg_lambda":       1.5,
    "random_state":     42,
    "n_jobs":           -1,
    "early_stopping_rounds": 50,
}

# Map each horizon to its params
XGB_PARAMS_BY_HORIZON = {
    "t1": XGB_PARAMS_BASE,
    "t3": XGB_PARAMS_BASE,
    "t7": XGB_PARAMS_T7,
}

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── Load features ───────────────────────────────────────────
print("📂  Loading features...")
df = pd.read_csv(FEATURES, parse_dates=["date"], index_col="date")
print(f"   Shape: {df.shape}  ({df.index.min().date()} → {df.index.max().date()})")

target_cols = [c for c in df.columns if c.startswith(("pm25_t", "alert_t"))]
feature_cols = [c for c in df.columns if c not in target_cols]
print(f"   Features: {len(feature_cols)}")

# ── Chronological split ─────────────────────────────────────
df_train = df[df.index <= TRAIN_END]
df_val   = df[(df.index > TRAIN_END) & (df.index <= VAL_END)]
df_test  = df[df.index > VAL_END]

print(f"\n   Train: {len(df_train):,} rows  ({df_train.index.min().date()} → {df_train.index.max().date()})")
print(f"   Val  : {len(df_val):,} rows  ({df_val.index.min().date()} → {df_val.index.max().date()})")
print(f"   Test : {len(df_test):,} rows  ({df_test.index.min().date()} → {df_test.index.max().date()})")

# ── MLflow setup ────────────────────────────────────────────
mlflow.set_tracking_uri(os.path.join(BASE, "..", "mlruns"))
mlflow.set_experiment("CAAS-XGBoost")

all_results = {}

# ── Train per horizon ───────────────────────────────────────
for horizon, (reg_target, cls_target) in HORIZONS.items():
    print(f"\n{'='*60}")
    print(f"🎯  Horizon {horizon.upper()} — target: {reg_target}")

    XGB_PARAMS = XGB_PARAMS_BY_HORIZON[horizon]
    if horizon == "t7":
        print(f"   Using tuned t+7 params: depth={XGB_PARAMS['max_depth']}, "
              f"n_est={XGB_PARAMS['n_estimators']}, lr={XGB_PARAMS['learning_rate']}")

    # Prepare sets
    def prep(split):
        sub = split[[*feature_cols, reg_target, cls_target]].dropna(subset=[reg_target])
        X = sub[feature_cols]
        y_reg = sub[reg_target]
        y_cls = sub[cls_target].astype(int)
        return X, y_reg, y_cls

    X_train, y_train, y_cls_train = prep(df_train)
    X_val,   y_val,   y_cls_val   = prep(df_val)
    X_test,  y_test,  y_cls_test  = prep(df_test)

    print(f"   Train: {len(X_train):,}  Val: {len(X_val):,}  Test: {len(X_test):,}")

    # Handle missing features with median imputation from training set
    train_medians = X_train.median()
    X_train = X_train.fillna(train_medians)
    X_val   = X_val.fillna(train_medians)
    X_test  = X_test.fillna(train_medians)

    with mlflow.start_run(run_name=f"XGBoost-{horizon}"):
        mlflow.log_params({**XGB_PARAMS_BY_HORIZON[horizon], "horizon": horizon,
                           "train_end": TRAIN_END, "val_end": VAL_END,
                           "n_features": len(feature_cols)})

        # Train regressor
        model = xgb.XGBRegressor(**XGB_PARAMS)
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        # Regression metrics
        def reg_metrics(X, y, split_name):
            pred = model.predict(X)
            pred = np.clip(pred, 0, None)   # PM2.5 cannot be negative
            mae  = mean_absolute_error(y, pred)
            rmse = np.sqrt(mean_squared_error(y, pred))
            r2   = r2_score(y, pred)
            return pred, {"mae": mae, "rmse": rmse, "r2": r2}

        pred_val,  metrics_val  = reg_metrics(X_val,  y_val,  "val")
        pred_test, metrics_test = reg_metrics(X_test, y_test, "test")

        # Alert classification (threshold > 50)
        def alert_metrics(pred, y_cls, split_name):
            pred_cls = (pred > ALERT_THRESHOLD).astype(int)
            if y_cls.sum() == 0:
                return {}
            return {
                "precision": precision_score(y_cls, pred_cls, zero_division=0),
                "recall":    recall_score(y_cls, pred_cls, zero_division=0),
                "f1":        f1_score(y_cls, pred_cls, zero_division=0),
                "auroc":     roc_auc_score(y_cls, pred),
            }

        alert_val  = alert_metrics(pred_val,  y_cls_val,  "val")
        alert_test = alert_metrics(pred_test, y_cls_test, "test")

        # Log metrics
        for k, v in metrics_val.items():
            mlflow.log_metric(f"val_{k}", v)
        for k, v in metrics_test.items():
            mlflow.log_metric(f"test_{k}", v)
        for k, v in alert_test.items():
            mlflow.log_metric(f"test_alert_{k}", v)

        # Feature importance (top 15)
        importance = pd.Series(
            model.feature_importances_, index=feature_cols
        ).sort_values(ascending=False)

        print(f"\n   📊 Validation  — MAE: {metrics_val['mae']:.2f}  RMSE: {metrics_val['rmse']:.2f}  R²: {metrics_val['r2']:.3f}")
        print(f"   📊 Test        — MAE: {metrics_test['mae']:.2f}  RMSE: {metrics_test['rmse']:.2f}  R²: {metrics_test['r2']:.3f}")
        if alert_test:
            print(f"   🚨 Test Alert  — Precision: {alert_test['precision']:.3f}  Recall: {alert_test['recall']:.3f}  F1: {alert_test['f1']:.3f}")

        print(f"\n   Top 10 features:")
        for feat, imp in importance.head(10).items():
            print(f"     {feat:<35} {imp:.4f}")

        # Save model
        model_path = os.path.join(MODELS_DIR, f"xgboost_{horizon}.json")
        model.save_model(model_path)
        mlflow.xgboost.log_model(model, f"model_{horizon}")

        # Save predictions
        pred_df = pd.DataFrame({
            "date":      X_test.index,
            "actual":    y_test.values,
            "predicted": pred_test,
            "alert_actual":    y_cls_test.values,
            "alert_predicted": (pred_test > ALERT_THRESHOLD).astype(int),
        })
        pred_path = os.path.join(RESULTS_DIR, f"xgboost_{horizon}_test_predictions.csv")
        pred_df.to_csv(pred_path, index=False)

        # Save importance
        imp_path = os.path.join(RESULTS_DIR, f"xgboost_{horizon}_importance.csv")
        importance.reset_index().rename(columns={"index": "feature", 0: "importance"}).to_csv(imp_path, index=False)

        mlflow.log_artifact(pred_path)
        mlflow.log_artifact(imp_path)

        all_results[horizon] = {
            "val":        metrics_val,
            "test":       metrics_test,
            "alert_test": alert_test,
        }

# ── Final summary ───────────────────────────────────────────
print(f"\n{'='*60}")
print("📋  FINAL RESULTS SUMMARY")
print(f"{'='*60}")
print(f"{'Horizon':<10} {'Split':<8} {'MAE':>7} {'RMSE':>7} {'R²':>7} {'F1':>7}")
print("-" * 50)
for h, res in all_results.items():
    for split in ["val", "test"]:
        m = res[split]
        f1 = res.get("alert_test", {}).get("f1", float("nan")) if split == "test" else float("nan")
        print(f"{h:<10} {split:<8} {m['mae']:>7.2f} {m['rmse']:>7.2f} {m['r2']:>7.3f} {f1:>7.3f}")

results_path = os.path.join(RESULTS_DIR, "xgboost_summary.json")
with open(results_path, "w") as f:
    json.dump(all_results, f, indent=2)
print(f"\n✅  Results saved: {results_path}")
print("✅  MLflow runs logged — run 'mlflow ui' to explore")
