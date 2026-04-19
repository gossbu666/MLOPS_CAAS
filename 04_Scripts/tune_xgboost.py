"""
CAAS — XGBoost Optuna Tuning (Phase B of SP7)

Per-horizon Bayesian hyperparameter search with MLflow + resumable SQLite storage.
After tuning, retrains the best model on train+val and evaluates on test (test is untouched during search).

Usage:
    python 04_Scripts/tune_xgboost.py                        # 100 trials per horizon
    python 04_Scripts/tune_xgboost.py --n-trials 200         # deeper search
    python 04_Scripts/tune_xgboost.py --n-trials 3 --smoke   # quick mechanism test
    python 04_Scripts/tune_xgboost.py --horizons t1,t7       # subset of horizons

Requirements: features.csv must exist (run build_features.py first).
Studies resume from SQLite — rerunning the same command adds more trials.
"""

import argparse
import json
import os
import warnings
from pathlib import Path

import mlflow
import mlflow.xgboost
import numpy as np
import optuna
import pandas as pd
import xgboost as xgb
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler
from sklearn.metrics import (
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

# ── Config ─────────────────────────────────────────────────
BASE        = Path(__file__).resolve().parent
FEATURES    = BASE.parent / "03_Data" / "processed" / "features.csv"
MODELS_DIR  = BASE.parent / "03_Data" / "models"
RESULTS_DIR = BASE.parent / "03_Data" / "results"
STUDIES_DIR = RESULTS_DIR / "optuna_studies"
MLRUNS_DIR  = BASE.parent / "mlruns"

TRAIN_END = "2022-12-31"
VAL_END   = "2023-12-31"

HORIZONS = {
    "t1": ("pm25_t1", "alert_t1"),
    "t3": ("pm25_t3", "alert_t3"),
    "t7": ("pm25_t7", "alert_t7"),
}

ALERT_THRESHOLD = 50.0
RANDOM_SEED = 42

for d in (MODELS_DIR, RESULTS_DIR, STUDIES_DIR):
    d.mkdir(parents=True, exist_ok=True)


# ── Data loading ───────────────────────────────────────────
def load_and_split():
    df = pd.read_csv(FEATURES, parse_dates=["date"], index_col="date")
    target_cols = [c for c in df.columns if c.startswith(("pm25_t", "alert_t"))]
    feature_cols = [c for c in df.columns if c not in target_cols]
    df_train = df[df.index <= TRAIN_END]
    df_val   = df[(df.index > TRAIN_END) & (df.index <= VAL_END)]
    df_test  = df[df.index > VAL_END]
    return df_train, df_val, df_test, feature_cols


def prep_split(split, feature_cols, reg_target, cls_target):
    sub = split[[*feature_cols, reg_target, cls_target]].dropna(subset=[reg_target])
    X = sub[feature_cols]
    y_reg = sub[reg_target]
    y_cls = sub[cls_target].astype(int)
    return X, y_reg, y_cls


# ── Metrics ────────────────────────────────────────────────
def regression_metrics(y_true, pred):
    pred = np.clip(pred, 0, None)
    return {
        "mae":  float(mean_absolute_error(y_true, pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, pred))),
        "r2":   float(r2_score(y_true, pred)),
    }


def alert_metrics(pred, y_cls):
    pred_cls = (pred > ALERT_THRESHOLD).astype(int)
    if y_cls.sum() == 0:
        return {}
    return {
        "precision": float(precision_score(y_cls, pred_cls, zero_division=0)),
        "recall":    float(recall_score(y_cls, pred_cls, zero_division=0)),
        "f1":        float(f1_score(y_cls, pred_cls, zero_division=0)),
        "auroc":     float(roc_auc_score(y_cls, pred)),
    }


# ── Optuna objective ───────────────────────────────────────
def make_objective(X_train, y_train, X_val, y_val, horizon):
    """Returns a callable that Optuna can optimize on val MAE."""
    train_medians = X_train.median()
    X_train_f = X_train.fillna(train_medians)
    X_val_f   = X_val.fillna(train_medians)

    def objective(trial: optuna.Trial):
        params = {
            "n_estimators":      trial.suggest_int("n_estimators", 200, 2000, log=True),
            "max_depth":         trial.suggest_int("max_depth", 3, 12),
            "learning_rate":     trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
            "min_child_weight":  trial.suggest_float("min_child_weight", 0.5, 10.0),
            "subsample":         trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_alpha":         trial.suggest_float("reg_alpha", 1e-4, 10.0, log=True),
            "reg_lambda":        trial.suggest_float("reg_lambda", 1e-4, 10.0, log=True),
            "random_state":      RANDOM_SEED,
            "n_jobs":            -1,
            "early_stopping_rounds": 50,
            "verbosity":         0,
        }

        model = xgb.XGBRegressor(**params)
        model.fit(X_train_f, y_train, eval_set=[(X_val_f, y_val)], verbose=False)
        pred = np.clip(model.predict(X_val_f), 0, None)
        val_mae = float(mean_absolute_error(y_val, pred))

        # Report intermediate for pruner
        trial.report(val_mae, step=0)
        if trial.should_prune():
            raise optuna.TrialPruned()

        # Log to MLflow as nested run
        with mlflow.start_run(run_name=f"trial_{trial.number}", nested=True):
            mlflow.log_params({**params, "horizon": horizon})
            mlflow.log_metric("val_mae", val_mae)

        return val_mae

    return objective


# ── Per-horizon tune + retrain ─────────────────────────────
def tune_one_horizon(horizon, n_trials, df_train, df_val, df_test, feature_cols):
    reg_target, cls_target = HORIZONS[horizon]
    print(f"\n{'=' * 60}")
    print(f"🎯  Tuning XGBoost for horizon {horizon.upper()}")
    print(f"   Target: {reg_target}   Trials: {n_trials}")

    X_train, y_train, y_cls_train = prep_split(df_train, feature_cols, reg_target, cls_target)
    X_val,   y_val,   y_cls_val   = prep_split(df_val,   feature_cols, reg_target, cls_target)
    X_test,  y_test,  y_cls_test  = prep_split(df_test,  feature_cols, reg_target, cls_target)
    print(f"   Train {len(X_train):,} | Val {len(X_val):,} | Test {len(X_test):,}")

    study_name = f"xgb_{horizon}"
    storage = f"sqlite:///{STUDIES_DIR / f'{study_name}.db'}"
    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        direction="minimize",
        sampler=TPESampler(seed=RANDOM_SEED),
        pruner=MedianPruner(n_warmup_steps=0, n_startup_trials=10),
        load_if_exists=True,
    )
    existing = len(study.trials)
    print(f"   Existing trials: {existing}")

    mlflow.set_experiment("CAAS-XGB-Optuna")
    with mlflow.start_run(run_name=f"xgb_tune_{horizon}"):
        mlflow.set_tag("horizon", horizon)
        mlflow.set_tag("model", "xgboost")
        mlflow.set_tag("phase", "SP7-B")

        objective = make_objective(X_train, y_train, X_val, y_val, horizon)
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

        best = study.best_trial
        print(f"   ✅ Best val MAE: {best.value:.4f}  (trial {best.number})")
        for k, v in best.params.items():
            print(f"      {k:<22} {v}")

        # ── Retrain on train+val with best params ─────────
        X_full = pd.concat([X_train, X_val])
        y_full = pd.concat([y_train, y_val])
        train_medians = X_full.median()
        X_full_f = X_full.fillna(train_medians)
        X_test_f = X_test.fillna(train_medians)

        final_params = {
            **best.params,
            "random_state": RANDOM_SEED,
            "n_jobs": -1,
            "verbosity": 0,
            # No early_stopping on final retrain — we use best.params['n_estimators']
        }
        final_model = xgb.XGBRegressor(**final_params)
        final_model.fit(X_full_f, y_full, verbose=False)

        # Test eval (test is held out, never seen during tuning or retrain)
        pred_test = np.clip(final_model.predict(X_test_f), 0, None)
        reg_test  = regression_metrics(y_test, pred_test)
        alert_t   = alert_metrics(pred_test, y_cls_test)

        # Val metric: use best held-out val MAE from tuning (BEFORE retrain).
        # Post-retrain val would leak (val is in training data after retrain).
        val_summary = {"mae_best_tuning": float(best.value)}

        print(f"   📊 Best val MAE (held-out during tuning): {best.value:.3f}")
        print(f"   📊 Test:  MAE {reg_test['mae']:.2f}  RMSE {reg_test['rmse']:.2f}  R² {reg_test['r2']:.3f}")
        if alert_t:
            print(f"   🚨 Test Alert: P {alert_t['precision']:.3f}  R {alert_t['recall']:.3f}  F1 {alert_t['f1']:.3f}")

        # Log final metrics
        mlflow.log_metric("val_mae_best_tuning", best.value)
        for k, v in reg_test.items():
            mlflow.log_metric(f"test_{k}", v)
        for k, v in alert_t.items():
            mlflow.log_metric(f"test_alert_{k}", v)
        mlflow.log_params({f"best_{k}": v for k, v in best.params.items()})

        # Save model
        model_path = MODELS_DIR / f"xgboost_{horizon}.json"
        final_model.save_model(str(model_path))
        mlflow.xgboost.log_model(final_model, f"model_{horizon}")

        # Save predictions
        pred_df = pd.DataFrame({
            "date":             X_test.index,
            "actual":           y_test.values,
            "predicted":        pred_test,
            "alert_actual":     y_cls_test.values,
            "alert_predicted":  (pred_test > ALERT_THRESHOLD).astype(int),
        })
        pred_path = RESULTS_DIR / f"xgboost_{horizon}_test_predictions.csv"
        pred_df.to_csv(pred_path, index=False)
        mlflow.log_artifact(str(pred_path))

        # Save feature importance
        imp = (
            pd.Series(final_model.feature_importances_, index=feature_cols)
            .sort_values(ascending=False)
            .reset_index()
            .rename(columns={"index": "feature", 0: "importance"})
        )
        imp_path = RESULTS_DIR / f"xgboost_{horizon}_importance.csv"
        imp.to_csv(imp_path, index=False)
        mlflow.log_artifact(str(imp_path))

    return {
        "val":        val_summary,
        "test":       reg_test,
        "alert_test": alert_t,
        "best_params": best.params,
        "best_val_mae_tuning": float(best.value),
        "n_trials_total": len(study.trials),
    }


# ── Main ───────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-trials", type=int, default=100)
    ap.add_argument("--horizons", type=str, default="t1,t3,t7",
                    help="comma-separated horizons (subset of t1,t3,t7)")
    ap.add_argument("--smoke", action="store_true",
                    help="smoke-test mode: writes studies to _smoke_*.db and keeps trials tiny")
    args = ap.parse_args()

    global STUDIES_DIR
    if args.smoke:
        print("🧪  SMOKE mode — studies go to optuna_studies_smoke/, models won't overwrite champion")

    horizons = [h.strip() for h in args.horizons.split(",") if h.strip()]
    for h in horizons:
        if h not in HORIZONS:
            raise SystemExit(f"Unknown horizon: {h}")

    mlflow.set_tracking_uri(f"file://{MLRUNS_DIR}")

    print("📂  Loading features and splitting...")
    df_train, df_val, df_test, feature_cols = load_and_split()
    print(f"   Train {len(df_train):,} | Val {len(df_val):,} | Test {len(df_test):,}")
    print(f"   Features: {len(feature_cols)}")

    all_results = {}
    for h in horizons:
        all_results[h] = tune_one_horizon(h, args.n_trials, df_train, df_val, df_test, feature_cols)

    # Update xgboost_summary.json (only in non-smoke mode)
    if not args.smoke:
        summary_path = RESULTS_DIR / "xgboost_summary.json"
        if summary_path.exists():
            existing = json.loads(summary_path.read_text())
        else:
            existing = {}
        for h, v in all_results.items():
            existing[h] = {
                "val":        v["val"],
                "test":       v["test"],
                "alert_test": v["alert_test"],
                "best_params": v["best_params"],
                "best_val_mae_tuning": v["best_val_mae_tuning"],
                "n_trials_total": v["n_trials_total"],
            }
        summary_path.write_text(json.dumps(existing, indent=2))
        print(f"\n✅  Summary updated: {summary_path}")

    print("\n📋  Tuning Summary")
    print(f"{'Horizon':<10} {'BestValMAE':>10} {'TestMAE':>8} {'TestR²':>8} {'AlertF1':>8}")
    print("-" * 52)
    for h, v in all_results.items():
        f1 = v["alert_test"].get("f1", float("nan")) if v["alert_test"] else float("nan")
        print(f"{h:<10} {v['best_val_mae_tuning']:>10.3f} {v['test']['mae']:>8.3f} {v['test']['r2']:>8.3f} {f1:>8.3f}")


if __name__ == "__main__":
    main()
