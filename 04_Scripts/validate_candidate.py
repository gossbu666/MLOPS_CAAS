"""
CAAS — Champion/Challenger Validation Gate
Compares newly trained candidate model against the current champion.
Exits with code 1 (blocks promotion) if candidate doesn't meet the bar.

Called by: .github/workflows/retrain.yml  step [4/6]

Validation criteria (all must pass):
    1. Candidate test MAE improves by >= min_mae_improvement (default 5%)
    2. Candidate alert F1 >= min_alert_f1 (default 0.75)
    3. Candidate evaluated on a recent validation window

Usage:
    python validate_candidate.py
    python validate_candidate.py --min-mae-improvement 0.03 --min-alert-f1 0.70
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, f1_score

import xgboost as xgb

# ── Paths ───────────────────────────────────────────────────
BASE        = os.path.dirname(os.path.abspath(__file__))
FEATURES    = os.path.join(BASE, "..", "03_Data", "processed", "features.csv")
MODELS_DIR  = os.path.join(BASE, "..", "03_Data", "models")
RESULTS_DIR = os.path.join(BASE, "..", "03_Data", "results")

ALERT_THRESHOLD = 50.0


def evaluate_model(model_path: str, X: pd.DataFrame, y_reg: pd.Series,
                   y_cls: pd.Series, train_medians: pd.Series) -> dict:
    """Load a model and evaluate on the given split."""
    model = xgb.XGBRegressor()
    model.load_model(model_path)

    X_filled = X.fillna(train_medians).fillna(0)

    # Align features
    expected = model.get_booster().feature_names
    if expected:
        for col in expected:
            if col not in X_filled.columns:
                X_filled[col] = 0.0
        X_filled = X_filled[expected]

    pred = np.clip(model.predict(X_filled), 0, None)
    pred_cls = (pred > ALERT_THRESHOLD).astype(int)

    mae  = mean_absolute_error(y_reg, pred)
    f1   = f1_score(y_cls, pred_cls, zero_division=0)

    return {"mae": mae, "f1": f1, "n_samples": len(y_reg)}


def main():
    parser = argparse.ArgumentParser(description="Validate candidate vs champion model")
    parser.add_argument("--min-mae-improvement", type=float, default=0.05,
                        help="Minimum relative MAE improvement (default: 5%%)")
    parser.add_argument("--min-alert-f1", type=float, default=0.75,
                        help="Minimum alert F1 score (default: 0.75)")
    parser.add_argument("--validation-window-days", type=int, default=90,
                        help="Most recent N days to use as validation window")
    args = parser.parse_args()

    print("=" * 60)
    print("  CAAS — Validation Gate")
    print(f"  Criteria: MAE improvement >= {args.min_mae_improvement*100:.0f}%"
          f"  |  Alert F1 >= {args.min_alert_f1:.2f}")
    print("=" * 60)

    # ── Load features ────────────────────────────────────────
    df = pd.read_csv(FEATURES, parse_dates=["date"], index_col="date")
    target_cols  = [c for c in df.columns if c.startswith(("pm25_t", "alert_t"))]
    feature_cols = [c for c in df.columns if c not in target_cols]

    # Validation window = most recent N days (after training cutoff)
    val_window = df.tail(args.validation_window_days)

    train_medians = df[df.index <= "2022-12-31"][feature_cols].median()

    gate_passed  = True
    gate_reasons = []

    for horizon in ["t1", "t3", "t7"]:
        reg_target = f"pm25_{horizon}"
        cls_target = f"alert_{horizon}"

        df_h = val_window[[*feature_cols, reg_target, cls_target]].dropna(subset=[reg_target])
        if len(df_h) < 30:
            print(f"\n⚠️  {horizon}: Not enough rows in validation window ({len(df_h)}). Skipping.")
            continue

        X     = df_h[feature_cols]
        y_reg = df_h[reg_target]
        y_cls = df_h[cls_target].astype(int)

        print(f"\n── Horizon {horizon.upper()} ──  ({len(df_h)} validation samples)")

        # Evaluate candidate (newly trained model)
        candidate_path = os.path.join(MODELS_DIR, f"xgboost_{horizon}.json")
        if not os.path.exists(candidate_path):
            msg = f"  ❌  Candidate model not found: {candidate_path}"
            print(msg)
            gate_reasons.append(msg)
            gate_passed = False
            continue

        cand = evaluate_model(candidate_path, X, y_reg, y_cls, train_medians)
        print(f"   Candidate  — MAE: {cand['mae']:.3f}  F1: {cand['f1']:.3f}")

        # Load champion metrics from summary JSON for comparison
        summary_path = os.path.join(RESULTS_DIR, "xgboost_summary.json")
        champion_mae = None
        if os.path.exists(summary_path):
            with open(summary_path) as f:
                summary = json.load(f)
            champion_mae = summary.get(horizon, {}).get("test", {}).get("mae")

        if champion_mae:
            rel_improvement = (champion_mae - cand["mae"]) / champion_mae
            print(f"   Champion   — MAE: {champion_mae:.3f} (from test set)")
            print(f"   MAE improvement: {rel_improvement*100:+.1f}%  (required: +{args.min_mae_improvement*100:.0f}%)")

            if rel_improvement < args.min_mae_improvement:
                msg = (f"  ⛔  {horizon}: MAE improvement {rel_improvement*100:.1f}% "
                       f"< required {args.min_mae_improvement*100:.0f}%")
                print(msg)
                gate_reasons.append(msg)
                gate_passed = False
            else:
                print(f"   ✅  MAE gate passed")
        else:
            print(f"   ⚠️  No champion MAE found — skipping MAE gate for {horizon}")

        n_alerts = int(y_cls.sum())
        if n_alerts == 0:
            print(f"   ⚠️  F1 gate skipped — no alert days in validation window "
                  f"({args.validation_window_days} days). Seasonal gap, not a failure.")
        elif cand["f1"] < args.min_alert_f1:
            msg = (f"  ⛔  {horizon}: Alert F1 {cand['f1']:.3f} "
                   f"< required {args.min_alert_f1:.2f}")
            print(msg)
            gate_reasons.append(msg)
            gate_passed = False
        else:
            print(f"   ✅  F1 gate passed  ({cand['f1']:.3f} >= {args.min_alert_f1:.2f})")

    # ── Final decision ────────────────────────────────────────
    print(f"\n{'='*60}")
    if gate_passed:
        print("✅  VALIDATION GATE PASSED — candidate can be promoted to Production")
        sys.exit(0)
    else:
        print("⛔  VALIDATION GATE FAILED — champion model unchanged")
        for reason in gate_reasons:
            print(reason)
        sys.exit(1)


if __name__ == "__main__":
    main()
