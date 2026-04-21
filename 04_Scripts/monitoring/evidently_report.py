"""
CAAS — Evidently AI Weekly Drift Monitoring
Runs as a scheduled GitHub Actions job (weekly).
Compares current feature distribution against training baseline.

Drift signals:
  - PSI > 0.2       → data drift flag
  - KS test p < 0.05 → residual concept drift flag

Output:
  - HTML report saved to 03_Data/results/drift_report_<date>.html
  - drift_summary.json with current drift status
  - Triggers GitHub Actions retraining workflow if any threshold exceeded

Usage:
    python evidently_report.py [--trigger-retrain] [--strict-exit]
"""

import os
import sys
import json
import argparse
import warnings
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# ── Config ─────────────────────────────────────────────────
BASE        = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(BASE)
DATA_DIR    = os.path.join(SCRIPTS_DIR, "..", "03_Data")
FEATURES    = os.path.join(DATA_DIR, "processed", "features.csv")
RESULTS_DIR = os.path.join(DATA_DIR, "results")
TRAIN_END   = "2022-12-31"
WINDOW_DAYS = 30       # Compare last 30 days against training distribution

PSI_THRESHOLD       = 0.20
KS_P_THRESHOLD      = 0.05
MAE_ROLL_THRESHOLD  = 15.0   # µg/m³ — trigger if 7-day rolling MAE exceeds this
MIN_TRAIN_POINTS    = 30
MIN_RECENT_POINTS   = 5
ZERO_INFLATION_THRESHOLD = 0.80
MIN_CORE_DRIFT_FLAGS = 2

MONITOR_FEATURES = [
    "pm25_lag1", "wind_speed", "hotspot_50km",
    "pm25_roll7_mean", "is_haze_season",
]

# Core signals drive retraining, while seasonal/calendar features are softer signals.
CORE_TRIGGER_FEATURES = {"pm25_lag1", "pm25_roll7_mean"}
SEASONAL_KS_FEATURES = {"wind_speed", "hotspot_50km", "is_haze_season"}
NON_TRIGGER_FEATURES = {"is_haze_season"}

os.makedirs(RESULTS_DIR, exist_ok=True)

def compute_psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index between two distributions."""
    eps = 1e-8
    expected = expected[~np.isnan(expected)]
    actual   = actual[~np.isnan(actual)]
    if len(expected) == 0 or len(actual) == 0:
        return 0.0
    bins_edges = np.percentile(expected, np.linspace(0, 100, bins + 1))
    bins_edges = np.unique(bins_edges)
    if len(bins_edges) < 2:
        return 0.0
    e_counts, _ = np.histogram(expected, bins=bins_edges)
    a_counts, _ = np.histogram(actual,   bins=bins_edges)
    e_pct = e_counts / (e_counts.sum() + eps)
    a_pct = a_counts / (a_counts.sum() + eps)
    psi = np.sum((a_pct - e_pct) * np.log((a_pct + eps) / (e_pct + eps)))
    return float(psi)

def compute_ks(train_vals: np.ndarray, recent_vals: np.ndarray):
    """Kolmogorov-Smirnov test between two samples."""
    from scipy import stats
    stat, pvalue = stats.ks_2samp(
        train_vals[~np.isnan(train_vals)],
        recent_vals[~np.isnan(recent_vals)],
    )
    return float(stat), float(pvalue)

def main(trigger_retrain: bool = False, strict_exit: bool = False):
    print("🔍  CAAS Evidently Drift Monitor")
    print(f"    Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"    Monitoring window: last {WINDOW_DAYS} days")
    print()

    # ── Load feature data ───────────────────────────────────
    if not os.path.exists(FEATURES):
        print("❌  features.csv not found — run build_features.py first")
        sys.exit(1)

    df = pd.read_csv(FEATURES, parse_dates=["date"], index_col="date")
    df_train  = df[df.index <= TRAIN_END]
    df_recent = df[df.index > TRAIN_END].tail(WINDOW_DAYS)

    print(f"    Training baseline: {len(df_train):,} rows ({df_train.index.min().date()} → {df_train.index.max().date()})")
    print(f"    Recent window:     {len(df_recent):,} rows ({df_recent.index.min().date()} → {df_recent.index.max().date()})")
    print()

    # Build seasonal reference rows (same month/day as current window in prior years)
    recent_month_day = {(d.month, d.day) for d in df_recent.index}
    df_train_seasonal = df_train[[
        (d.month, d.day) in recent_month_day for d in df_train.index
    ]]

    # ── Compute PSI + KS for each monitored feature ─────────
    drift_results = []
    core_drift_features = set()
    soft_drift_features = set()
    any_psi_drift = False
    any_ks_drift  = False

    print(f"{'Feature':<22} {'PSI':>8} {'PSI flag':>10} {'KS stat':>10} {'KS p':>10} {'KS ref':>8} {'KS flag':>10}")
    print("-" * 92)

    for feat in MONITOR_FEATURES:
        if feat not in df.columns:
            continue
        train_vals  = df_train[feat].dropna().values
        recent_vals = df_recent[feat].dropna().values
        if len(train_vals) < MIN_TRAIN_POINTS or len(recent_vals) < MIN_RECENT_POINTS:
            continue

        psi = compute_psi(train_vals, recent_vals)

        ks_train_vals = train_vals
        ks_reference = "global"
        seasonal_train_vals = df_train_seasonal[feat].dropna().values
        if feat in SEASONAL_KS_FEATURES and len(seasonal_train_vals) >= MIN_TRAIN_POINTS:
            ks_train_vals = seasonal_train_vals
            ks_reference = "seasonal"
        ks_stat, ks_p = compute_ks(ks_train_vals, recent_vals)

        train_zero_ratio = float(np.mean(train_vals == 0))
        recent_zero_ratio = float(np.mean(recent_vals == 0))
        zero_inflated = (
            train_zero_ratio >= ZERO_INFLATION_THRESHOLD
            and recent_zero_ratio >= ZERO_INFLATION_THRESHOLD
        )

        psi_flag_raw = psi > PSI_THRESHOLD
        psi_flag = psi_flag_raw and not zero_inflated
        ks_flag  = ks_p < KS_P_THRESHOLD
        contributes_to_trigger = feat not in NON_TRIGGER_FEATURES

        if contributes_to_trigger and (psi_flag or ks_flag):
            if feat in CORE_TRIGGER_FEATURES:
                core_drift_features.add(feat)
            else:
                soft_drift_features.add(feat)

        if contributes_to_trigger and psi_flag:
            any_psi_drift = True
        if contributes_to_trigger and ks_flag:
            any_ks_drift = True

        if psi_flag:
            psi_marker = "⚠️ DRIFT"
        elif psi_flag_raw and zero_inflated:
            psi_marker = "⚪ ZI-skip"
        else:
            psi_marker = "✅ OK"

        drift_results.append({
            "feature":  feat,
            "psi":      round(psi, 4),
            "psi_flag": psi_flag,
            "ks_stat":  round(ks_stat, 4),
            "ks_p":     round(ks_p, 4),
            "ks_flag":  ks_flag,
            "ks_reference": ks_reference,
            "zero_inflated": zero_inflated,
            "contributes_to_trigger": contributes_to_trigger,
        })

        ks_marker  = "⚠️ DRIFT" if ks_flag  else "✅ OK"
        print(
            f"{feat:<22} {psi:>8.4f} {psi_marker:>10} {ks_stat:>10.4f} "
            f"{ks_p:>10.4f} {ks_reference:>8} {ks_marker:>10}"
        )

    print()

    core_drift_count = len(core_drift_features)
    soft_drift_count = len(soft_drift_features)
    if core_drift_count or soft_drift_count:
        print(
            f"Drift trigger counts — core: {core_drift_count} ({', '.join(sorted(core_drift_features)) or '-'}) | "
            f"soft: {soft_drift_count} ({', '.join(sorted(soft_drift_features)) or '-'})"
        )
        print()

    # ── Rolling MAE check ────────────────────────────────────
    mae_flag = False
    pred_files = [f for f in os.listdir(RESULTS_DIR) if f.startswith("xgboost_t1_test")]
    if pred_files:
        pred_path = os.path.join(RESULTS_DIR, pred_files[0])
        pred_df   = pd.read_csv(pred_path, parse_dates=["date"])
        recent_preds = pred_df.tail(7)
        if len(recent_preds) > 0:
            rolling_mae = (recent_preds["actual"] - recent_preds["predicted"]).abs().mean()
            mae_flag = rolling_mae > MAE_ROLL_THRESHOLD
            flag_str = "⚠️ HIGH" if mae_flag else "✅ OK"
            print(f"7-day rolling MAE (t+1): {rolling_mae:.2f} µg/m³  {flag_str}")
            print()

    # ── Summary ──────────────────────────────────────────────
    # Trigger policy:
    # - immediate if MAE degrades
    # - strong data drift if 2+ core features drift
    # - moderate drift if 1 core + 2+ soft features drift
    drift_strong = core_drift_count >= MIN_CORE_DRIFT_FLAGS
    drift_moderate = core_drift_count >= 1 and soft_drift_count >= 2
    retrain_needed = mae_flag or drift_strong or drift_moderate

    summary = {
        "timestamp":      datetime.now().isoformat(),
        "window_days":    WINDOW_DAYS,
        "psi_drift":      any_psi_drift,
        "ks_drift":       any_ks_drift,
        "mae_flag":       mae_flag,
        "retrain_needed": retrain_needed,
        "core_drift_count": core_drift_count,
        "soft_drift_count": soft_drift_count,
        "core_drift_features": sorted(core_drift_features),
        "soft_drift_features": sorted(soft_drift_features),
        "seasonal_reference_rows": int(len(df_train_seasonal)),
        "policy": {
            "min_core_drift_flags": MIN_CORE_DRIFT_FLAGS,
            "moderate_rule": "core>=1 and soft>=2",
            "non_trigger_features": sorted(NON_TRIGGER_FEATURES),
            "zero_inflation_threshold": ZERO_INFLATION_THRESHOLD,
        },
        "features":       drift_results,
    }

    # Convert numpy types to native Python for JSON serialisation
    def _to_python(obj):
        if isinstance(obj, dict):
            return {k: _to_python(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_to_python(v) for v in obj]
        if hasattr(obj, "item"):   # numpy scalar (bool_, int64, float64 …)
            return obj.item()
        return obj

    summary_path = os.path.join(RESULTS_DIR, "drift_summary.json")
    with open(summary_path, "w") as f:
        json.dump(_to_python(summary), f, indent=2)

    print("=" * 60)
    if retrain_needed:
        print("⚠️  DRIFT DETECTED — Retraining recommended")
        print(f"   PSI drift  : {'YES' if any_psi_drift else 'no'}")
        print(f"   KS drift   : {'YES' if any_ks_drift  else 'no'}")
        print(f"   MAE flag   : {'YES' if mae_flag       else 'no'}")
        print(f"   Core drift : {core_drift_count} feature(s)")
        print(f"   Soft drift : {soft_drift_count} feature(s)")
    else:
        print("✅  No significant drift detected — champion model OK")

    print(f"\n   Summary saved: {summary_path}")

    # ── Optionally trigger GitHub Actions retrain workflow ──
    if retrain_needed and trigger_retrain:
        gh_token = os.getenv("GITHUB_TOKEN")
        gh_repo  = os.getenv("GITHUB_REPOSITORY", "your-org/caas")
        if gh_token:
            url = f"https://api.github.com/repos/{gh_repo}/dispatches"
            payload = {
                "event_type": "drift-alert",
                "client_payload": {
                    "psi_drift": bool(any_psi_drift),
                    "ks_drift":  bool(any_ks_drift),
                    "mae_flag":  bool(mae_flag),
                    "timestamp": datetime.now().isoformat(),
                }
            }
            resp = requests.post(url,
                                 json=payload,
                                 headers={"Authorization": f"Bearer {gh_token}",
                                          "Accept": "application/vnd.github+json"})
            if resp.status_code == 204:
                print("   🚀  Retraining workflow triggered via GitHub API")
            else:
                print(f"   ⚠️  Failed to trigger retrain: HTTP {resp.status_code}")
        else:
            print("   ℹ️  GITHUB_TOKEN not set — skipping auto-trigger")

    # ── Try to generate Evidently HTML report ───────────────
    try:
        from evidently.report import Report
        from evidently.metric_preset import DataDriftPreset, DataQualityPreset

        available_features = [f for f in MONITOR_FEATURES if f in df.columns]
        valid_features = [
            f for f in available_features
            if df_train[f].notna().sum() >= MIN_TRAIN_POINTS
            and df_recent[f].notna().sum() >= MIN_RECENT_POINTS
        ]
        skipped_features = [f for f in available_features if f not in valid_features]

        if skipped_features:
            print(f"   ℹ️  Evidently skipped sparse features: {', '.join(skipped_features)}")

        if not valid_features:
            print("   ℹ️  Evidently report skipped: no monitored features with enough non-null data")
        else:
            report = Report(metrics=[DataDriftPreset(), DataQualityPreset()])
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning)
                report.run(
                    reference_data=df_train[valid_features],
                    current_data=df_recent[valid_features],
                )

            report_path = os.path.join(
                RESULTS_DIR,
                f"drift_report_{datetime.now().strftime('%Y%m%d')}.html"
            )
            report.save_html(report_path)
            print(f"   📄  Evidently HTML report: {report_path}")
    except ImportError:
        print("   ℹ️  evidently not installed — pip install evidently")
    except Exception as e:
        print(f"   ⚠️  Evidently report failed: {e}")

    return 1 if (strict_exit and retrain_needed) else 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trigger-retrain", action="store_true",
                        help="Trigger GitHub Actions retrain workflow if drift detected")
    parser.add_argument("--strict-exit", action="store_true",
                        help="Return exit code 1 when retraining is recommended (useful in CI)")
    args = parser.parse_args()
    sys.exit(main(trigger_retrain=args.trigger_retrain, strict_exit=args.strict_exit))
