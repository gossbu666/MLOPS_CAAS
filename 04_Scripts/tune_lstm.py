"""
CAAS — Optuna tuner for LSTM v2.

Objective: minimise VAL MAE (held-out) per horizon. Candidate trial spans
architecture + sequence length + core hyper-parameters. Resumable SQLite study,
MLflow nested trial logging.

Runtime: LSTM is slow on M4 tf-metal (~40–80s/epoch at 30-day seq_len).
         Recommended: smaller `--n-trials` and a tight `--epochs-per-trial`.

Usage:
    python tune_lstm.py --n-trials 30 --epochs-per-trial 25
    python tune_lstm.py --smoke        # 1 trial, 2 epochs, t1 only
"""

from __future__ import annotations

import argparse
import json
import os
import time
import warnings
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BKK = ZoneInfo("Asia/Bangkok")

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import mlflow
import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner

# Reuse the shared training function from train_lstm_v2
from train_lstm_v2 import (  # noqa: E402  (local module)
    HORIZONS,
    RESULTS_DIR,
    train_one,
)


BASE = os.path.dirname(os.path.abspath(__file__))
STUDIES_DIR = os.path.join(BASE, "..", "03_Data", "results", "optuna_studies")
os.makedirs(STUDIES_DIR, exist_ok=True)


# ───────────────────────────────────────────────────────────────────────────
#  Objective
# ───────────────────────────────────────────────────────────────────────────
def make_objective(horizon: str, epochs_per_trial: int, patience: int, total_trials: int):
    def objective(trial: optuna.Trial) -> float:
        arch = trial.suggest_categorical(
            "arch", ["stacked", "bidirectional", "attention", "cnn_lstm"]
        )
        seq_len = trial.suggest_categorical("seq_len", [7, 14, 21, 30])
        hidden_units = trial.suggest_categorical("hidden_units", [32, 64, 96, 128])
        num_layers = trial.suggest_int("num_layers", 1, 3)
        dropout = trial.suggest_float("dropout", 0.1, 0.4)
        learning_rate = trial.suggest_float("learning_rate", 1e-4, 3e-3, log=True)
        batch_size = trial.suggest_categorical("batch_size", [16, 32, 64])

        now = datetime.now(timezone.utc).astimezone(BKK).strftime("%H:%M:%S")
        print(
            f"   [{now}] ▶  Trial {trial.number + 1}/{total_trials}  "
            f"arch={arch} seq={seq_len} units={hidden_units} "
            f"layers={num_layers} drop={dropout:.2f} lr={learning_rate:.1e} bs={batch_size}",
            flush=True,
        )
        t0 = time.time()

        result = train_one(
            horizon,
            arch=arch,
            seq_len=seq_len,
            hidden_units=hidden_units,
            num_layers=num_layers,
            dropout=dropout,
            learning_rate=learning_rate,
            batch_size=batch_size,
            epochs=epochs_per_trial,
            patience=patience,
            save_artifacts=False,
            verbose=0,
        )
        val_mae = float(result["val"]["mae"])
        elapsed = time.time() - t0
        print(
            f"   [{datetime.now(timezone.utc).astimezone(BKK).strftime('%H:%M:%S')}] ✓  Trial {trial.number + 1} "
            f"val_MAE={val_mae:.3f}  test_MAE={result['test']['mae']:.3f}  "
            f"R²={result['test']['r2']:.3f}  ({elapsed:.0f}s)",
            flush=True,
        )

        with mlflow.start_run(run_name=f"trial_{trial.number}_{horizon}", nested=True):
            mlflow.log_params({
                "horizon": horizon,
                "arch": arch,
                "seq_len": seq_len,
                "hidden_units": hidden_units,
                "num_layers": num_layers,
                "dropout": dropout,
                "learning_rate": learning_rate,
                "batch_size": batch_size,
            })
            mlflow.log_metric("val_mae", val_mae)
            mlflow.log_metric("val_r2", result["val"]["r2"])
            mlflow.log_metric("test_mae", result["test"]["mae"])
            mlflow.log_metric("test_r2", result["test"]["r2"])
            if result["alert_test"]:
                mlflow.log_metric("test_alert_f1", result["alert_test"]["f1"])

        trial.report(val_mae, step=0)
        if trial.should_prune():
            raise optuna.TrialPruned()
        return val_mae

    return objective


# ───────────────────────────────────────────────────────────────────────────
#  Orchestration
# ───────────────────────────────────────────────────────────────────────────
def tune_horizon(
    horizon: str,
    n_trials: int,
    epochs_per_trial: int,
    patience: int,
    final_epochs: int,
) -> dict:
    study_path = os.path.join(STUDIES_DIR, f"lstm_{horizon}.db")
    storage = f"sqlite:///{study_path}"

    study = optuna.create_study(
        study_name=f"lstm_{horizon}",
        storage=storage,
        direction="minimize",
        sampler=TPESampler(seed=42),
        pruner=MedianPruner(n_warmup_steps=1),
        load_if_exists=True,
    )

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    mlflow.set_tracking_uri(os.path.join(BASE, "..", "mlruns"))
    mlflow.set_experiment("CAAS-LSTM-Tuning")

    with mlflow.start_run(run_name=f"optuna_lstm_{horizon}"):
        mlflow.log_params({
            "horizon": horizon,
            "n_trials": n_trials,
            "epochs_per_trial": epochs_per_trial,
            "patience": patience,
        })
        study.optimize(
            make_objective(horizon, epochs_per_trial, patience, n_trials),
            n_trials=n_trials,
            gc_after_trial=True,
        )

        best = study.best_trial
        print(f"\n🏆 Best {horizon}: val MAE {best.value:.3f}  params={best.params}")

        # Final retrain with best params and the full training budget
        final = train_one(
            horizon,
            arch=best.params["arch"],
            seq_len=best.params["seq_len"],
            hidden_units=best.params["hidden_units"],
            num_layers=best.params["num_layers"],
            dropout=best.params["dropout"],
            learning_rate=best.params["learning_rate"],
            batch_size=best.params["batch_size"],
            epochs=final_epochs,
            patience=patience * 2,
            save_artifacts=True,
            verbose=0,
        )

        # Honest val metric = tuning best.value (not the final retrain, which
        # may or may not touch val depending on policy — we keep val held out here)
        summary = {
            "horizon": horizon,
            "best_params": best.params,
            "best_val_mae_tuning": float(best.value),
            "val": final["val"],
            "test": final["test"],
            "alert_val": final["alert_val"],
            "alert_test": final["alert_test"],
            "n_trials_completed": len(study.trials),
            "study_path": study_path,
            "model_path": final.get("model_path"),
            "scaler_path": final.get("scaler_path"),
        }
        for k, v in final["val"].items():
            mlflow.log_metric(f"final_val_{k}", v)
        for k, v in final["test"].items():
            mlflow.log_metric(f"final_test_{k}", v)
        for k, v in final["alert_test"].items():
            mlflow.log_metric(f"final_test_alert_{k}", v)
        mlflow.log_metric("best_val_mae_tuning", float(best.value))

    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-trials", type=int, default=30)
    parser.add_argument("--horizons", default="t1,t3,t7")
    parser.add_argument("--epochs-per-trial", type=int, default=25)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--final-epochs", type=int, default=100)
    parser.add_argument("--smoke", action="store_true",
                        help="1 trial, 2 epochs, t1 only — sanity check")
    args = parser.parse_args()

    if args.smoke:
        args.n_trials = 1
        args.epochs_per_trial = 2
        args.patience = 2
        args.final_epochs = 2
        args.horizons = "t1"

    horizons = [h.strip() for h in args.horizons.split(",") if h.strip()]
    all_summaries = {}
    for h in horizons:
        assert h in HORIZONS, f"Unknown horizon: {h}"
        print(f"\n{'=' * 60}\n🎯  Tuning LSTM — horizon {h.upper()}\n{'=' * 60}")
        all_summaries[h] = tune_horizon(
            h,
            n_trials=args.n_trials,
            epochs_per_trial=args.epochs_per_trial,
            patience=args.patience,
            final_epochs=args.final_epochs,
        )

    out = os.path.join(RESULTS_DIR, "lstm_tuned_summary.json")
    with open(out, "w") as f:
        json.dump(all_summaries, f, indent=2, default=str)
    print(f"\n✅  Saved: {out}")


if __name__ == "__main__":
    main()
