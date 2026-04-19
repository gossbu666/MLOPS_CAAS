"""
CAAS — Final comparison table: every available model vs. two naive baselines.

Naive baselines (computed fresh from features.csv):
  * persistence — predict pm25_tH = pm25_t0
  * seasonal_7  — predict pm25_tH = pm25_{date - 7 days}  (weekly lag)

ML models read from existing test prediction CSVs in 03_Data/results/.

Output: Markdown + JSON summary. A row shows test MAE, RMSE, R², alert F1,
and — where available — the bootstrap 95 % CI on Δ MAE vs the persistence baseline.

Usage:
    python generate_comparison_table.py
"""

from __future__ import annotations

import json
import os
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import (
    f1_score, mean_absolute_error, mean_squared_error, r2_score,
    precision_score, recall_score,
)


BASE = os.path.dirname(os.path.abspath(__file__))
FEATURES_PATH = os.path.join(BASE, "..", "03_Data", "processed", "features.csv")
PM25_PATH = os.path.join(BASE, "..", "03_Data", "processed", "pm25_consolidated.csv")
RESULTS_DIR = os.path.join(BASE, "..", "03_Data", "results")

TRAIN_END = "2022-12-31"
VAL_END = "2023-12-31"
ALERT_THRESHOLD = 50.0

HORIZON_DAYS = {"t1": 1, "t3": 3, "t7": 7}

MODEL_CSVS = {
    "xgboost":   "xgboost_{h}_test_predictions.csv",
    "lightgbm":  "lightgbm_{h}_test_predictions.csv",
    "lstm_v1":   "lstm_{h}_test_predictions.csv",
    "lstm_v2":   "lstm_v2_{h}_test_predictions.csv",
}


def metrics_from_pred(df: pd.DataFrame) -> dict:
    y = df["actual"].values
    p = df["predicted"].values
    mae = float(mean_absolute_error(y, p))
    rmse = float(np.sqrt(mean_squared_error(y, p)))
    r2 = float(r2_score(y, p))
    y_cls = (y > ALERT_THRESHOLD).astype(int)
    p_cls = (p > ALERT_THRESHOLD).astype(int)
    alert = {}
    if y_cls.sum() > 0:
        alert = {
            "precision": float(precision_score(y_cls, p_cls, zero_division=0)),
            "recall":    float(recall_score(y_cls, p_cls, zero_division=0)),
            "f1":        float(f1_score(y_cls, p_cls, zero_division=0)),
        }
    return {"mae": mae, "rmse": rmse, "r2": r2, "alert": alert, "n": len(df)}


def build_naive_predictions(horizon: str) -> dict[str, pd.DataFrame]:
    """Compute persistence and seasonal-7 predictions from raw PM2.5 + targets."""
    pm = pd.read_csv(PM25_PATH, parse_dates=["date"])[["date", "pm25"]].sort_values("date")
    feats = pd.read_csv(FEATURES_PATH, parse_dates=["date"]).sort_values("date")
    target_col = f"pm25_{horizon}"
    df = feats[["date", target_col]].merge(pm, on="date", how="left")
    df = df.dropna(subset=["pm25", target_col]).reset_index(drop=True)

    test_mask = df["date"] > pd.Timestamp(VAL_END)

    # Persistence: prediction = today's pm25 (the horizon will equal today)
    persistence = pd.DataFrame({
        "date":      df.loc[test_mask, "date"].values,
        "actual":    df.loc[test_mask, target_col].values,
        "predicted": df.loc[test_mask, "pm25"].values,
    }).dropna()

    # Seasonal-7: predict pm25_{t+H} using the actual measurement 7 days prior to target date
    seasonal_pred = df[target_col].shift(7).values
    seasonal = pd.DataFrame({
        "date":      df.loc[test_mask, "date"].values,
        "actual":    df.loc[test_mask, target_col].values,
        "predicted": seasonal_pred[test_mask.values],
    }).dropna()

    return {"persistence": persistence, "seasonal_7": seasonal}


def paired_bootstrap_delta(a: pd.DataFrame, b: pd.DataFrame, n_resamples: int, rng: np.random.Generator):
    merged = pd.merge(
        a.assign(err_a=(a["predicted"] - a["actual"]).abs())[["date", "err_a"]],
        b.assign(err_b=(b["predicted"] - b["actual"]).abs())[["date", "err_b"]],
        on="date", how="inner",
    )
    if len(merged) == 0:
        return None
    delta = (merged["err_a"] - merged["err_b"]).values
    idx = rng.integers(0, len(delta), size=(n_resamples, len(delta)))
    means = delta[idx].mean(axis=1)
    return {
        "delta_mae": float(delta.mean()),
        "ci_low": float(np.percentile(means, 2.5)),
        "ci_high": float(np.percentile(means, 97.5)),
        "n_paired": int(len(delta)),
    }


def main():
    rng = np.random.default_rng(42)
    report: dict[str, dict] = {}
    md_lines: list[str] = []

    for h in HORIZON_DAYS:
        preds: dict[str, pd.DataFrame] = {}

        # Naive baselines
        naive = build_naive_predictions(h)
        preds.update(naive)

        # ML models (if prediction CSVs exist)
        for name, pattern in MODEL_CSVS.items():
            p = os.path.join(RESULTS_DIR, pattern.format(h=h))
            if os.path.exists(p):
                df = pd.read_csv(p, parse_dates=["date"]).sort_values("date")
                df = df[["date", "actual", "predicted"]].dropna()
                preds[name] = df

        report[h] = {}
        md_lines.append(f"\n### Horizon {h.upper()}\n")
        md_lines.append("| Model | MAE | RMSE | R² | Alert F1 | Δ MAE vs persistence (95 % CI) | n |")
        md_lines.append("|--|--:|--:|--:|--:|--:|--:|")

        persistence_df = preds.get("persistence")
        for name, df in preds.items():
            m = metrics_from_pred(df)
            cell_delta = "—"
            if persistence_df is not None and name != "persistence":
                bs = paired_bootstrap_delta(df, persistence_df, n_resamples=1000, rng=rng)
                if bs is not None:
                    report[h].setdefault(name, {})["bootstrap_vs_persistence"] = bs
                    sign = "✅" if bs["ci_high"] < 0 else ("⚠️" if bs["ci_low"] > 0 else "◻")
                    cell_delta = f"{bs['delta_mae']:+.2f}  [{bs['ci_low']:+.2f}, {bs['ci_high']:+.2f}] {sign}"
            row = (
                f"| {name} | {m['mae']:.2f} | {m['rmse']:.2f} | {m['r2']:.3f} "
                f"| {m['alert'].get('f1', float('nan')):.3f} | {cell_delta} | {m['n']} |"
            )
            md_lines.append(row)
            report[h].setdefault(name, {}).update({
                "mae": m["mae"], "rmse": m["rmse"], "r2": m["r2"],
                "alert": m["alert"], "n": m["n"],
            })

    out_json = os.path.join(RESULTS_DIR, "comparison_table.json")
    out_md = os.path.join(RESULTS_DIR, "comparison_table.md")
    with open(out_json, "w") as f:
        json.dump(report, f, indent=2)
    with open(out_md, "w") as f:
        f.write("# CAAS Final Model Comparison\n")
        f.write("\n✅ = model significantly better than persistence   "
                "⚠️ = worse   ◻ = indistinguishable (CI crosses 0)\n")
        f.write("\n".join(md_lines))

    print("\n".join(md_lines))
    print(f"\n✅  Saved: {out_json}")
    print(f"✅  Saved: {out_md}")


if __name__ == "__main__":
    main()
