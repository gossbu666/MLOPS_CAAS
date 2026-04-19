"""
CAAS — Paired bootstrap comparison of model test-set errors.

For every horizon and every model pair, resample the per-day absolute errors
with replacement (paired by date) and compute the 95 % CI on Δ MAE. If the
interval excludes 0 we can claim a statistically discernible difference.

Inputs — per-horizon test-prediction CSVs with columns [date, actual, predicted]:
  03_Data/results/xgboost_{h}_test_predictions.csv       (v1 / current champion)
  03_Data/results/lstm_{h}_test_predictions.csv          (v1 LSTM)
  03_Data/results/lstm_v2_{h}_test_predictions.csv       (optional)
  03_Data/results/xgboost_tuned_{h}_test_predictions.csv (optional)
  03_Data/results/lightgbm_tuned_{h}_test_predictions.csv(optional)

Missing files are skipped cleanly — no error.

Output: 03_Data/results/bootstrap_compare.json + printed table.

Usage:
    python bootstrap_compare.py
    python bootstrap_compare.py --n-resamples 5000
"""

from __future__ import annotations

import argparse
import json
import os
from itertools import combinations

import numpy as np
import pandas as pd


BASE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE, "..", "03_Data", "results")

HORIZONS = ["t1", "t3", "t7"]

CANDIDATES = {
    "xgboost":  "xgboost_{h}_test_predictions.csv",
    "lightgbm": "lightgbm_{h}_test_predictions.csv",
    "lstm_v1":  "lstm_{h}_test_predictions.csv",
    "lstm_v2":  "lstm_v2_{h}_test_predictions.csv",
}


def load_predictions(horizon: str) -> dict[str, pd.DataFrame]:
    loaded = {}
    for name, pattern in CANDIDATES.items():
        p = os.path.join(RESULTS_DIR, pattern.format(h=horizon))
        if not os.path.exists(p):
            continue
        df = pd.read_csv(p, parse_dates=["date"]).sort_values("date")
        df = df[["date", "actual", "predicted"]].dropna()
        df["abs_err"] = (df["predicted"] - df["actual"]).abs()
        loaded[name] = df
    return loaded


def paired_bootstrap_delta_mae(
    a: pd.DataFrame, b: pd.DataFrame, n_resamples: int, rng: np.random.Generator
) -> dict:
    """Return Δ MAE (a - b) point estimate plus 95 % CI."""
    merged = pd.merge(
        a[["date", "abs_err"]], b[["date", "abs_err"]],
        on="date", suffixes=("_a", "_b"), how="inner",
    )
    errs_a = merged["abs_err_a"].values
    errs_b = merged["abs_err_b"].values
    delta = errs_a - errs_b  # positive ⇒ model a worse
    n = len(delta)
    if n == 0:
        return {"delta_mae": None, "ci_low": None, "ci_high": None, "n_paired": 0}

    idx = rng.integers(0, n, size=(n_resamples, n))
    samples = delta[idx].mean(axis=1)
    return {
        "delta_mae": float(delta.mean()),
        "ci_low": float(np.percentile(samples, 2.5)),
        "ci_high": float(np.percentile(samples, 97.5)),
        "n_paired": int(n),
        "mae_a": float(errs_a.mean()),
        "mae_b": float(errs_b.mean()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-resamples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    out = {}

    print(f"\n{'='*80}")
    print(f"Paired bootstrap  (n_resamples={args.n_resamples})  — Δ MAE (a − b), 95 % CI")
    print(f"{'='*80}")
    print(f"{'horizon':<7} {'model_a':<14} {'model_b':<14} {'Δ MAE':>8} {'CI':>20} {'sig?':>6} {'n':>5}")
    print("-" * 80)

    for h in HORIZONS:
        preds = load_predictions(h)
        if len(preds) < 2:
            print(f"{h:<7} (only {len(preds)} model(s) available — skipping)")
            continue
        out[h] = {}
        for a_name, b_name in combinations(preds.keys(), 2):
            res = paired_bootstrap_delta_mae(preds[a_name], preds[b_name], args.n_resamples, rng)
            if res["delta_mae"] is None:
                continue
            sig = (res["ci_low"] > 0) or (res["ci_high"] < 0)
            ci = f"[{res['ci_low']:+.3f}, {res['ci_high']:+.3f}]"
            print(f"{h:<7} {a_name:<14} {b_name:<14} {res['delta_mae']:+8.3f} {ci:>20} {'YES' if sig else 'no':>6} {res['n_paired']:>5}")
            out[h][f"{a_name}__vs__{b_name}"] = res

    out_path = os.path.join(RESULTS_DIR, "bootstrap_compare.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n✅  Saved: {out_path}")


if __name__ == "__main__":
    main()
