"""
CAAS — SHAP Analysis for XGBoost Champion Models
Generates SHAP summary and waterfall plots for t+1, t+3, t+7.

Outputs (saved to both 03_Data/results/ and 07_Final/report/figures/):
  fig_shap_summary_t1.png   — beeswarm summary plot
  fig_shap_summary_t3.png
  fig_shap_summary_t7.png
  fig_shap_waterfall_t1.png — single-prediction waterfall (highest PM2.5 day)
  fig_shap_waterfall_t3.png
  fig_shap_waterfall_t7.png
  shap_summary.json          — mean |SHAP| per feature per horizon

Usage:
    pip install shap
    python shap_analysis.py
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import shap
except ImportError:
    raise SystemExit("Install shap first: pip install shap")

import xgboost as xgb

# ── Paths ───────────────────────────────────────────────────
BASE        = os.path.dirname(os.path.abspath(__file__))
FEATURES    = os.path.join(BASE, "..", "03_Data", "processed", "features.csv")
MODELS_DIR  = os.path.join(BASE, "..", "03_Data", "models")
RESULTS_DIR = os.path.join(BASE, "..", "03_Data", "results")
FIGURES_DIR = os.path.join(BASE, "..", "07_Final", "report", "figures")
os.makedirs(FIGURES_DIR, exist_ok=True)

TRAIN_END = "2022-12-31"
VAL_END   = "2023-12-31"
HORIZONS  = ["t1", "t3", "t7"]

# ── Load features ───────────────────────────────────────────
print("📂  Loading features...")
df = pd.read_csv(FEATURES, parse_dates=["date"], index_col="date")
target_cols  = [c for c in df.columns if c.startswith(("pm25_t", "alert_t"))]
feature_cols = [c for c in df.columns if c not in target_cols]

# Use test split only for SHAP (unseen data — more honest explanation)
df_test = df[df.index > VAL_END]

# Impute with training medians
train_medians = df[df.index <= TRAIN_END][feature_cols].median()
df_test_feat  = df_test[feature_cols].fillna(train_medians).fillna(0)

print(f"   Test set: {len(df_test_feat):,} rows, {len(feature_cols)} features")

shap_summary_out = {}

print("\n" + "=" * 60)
print("  CAAS — SHAP Analysis")
print("=" * 60)

for horizon in HORIZONS:
    reg_target = f"pm25_{horizon}"
    print(f"\n── Horizon {horizon.upper()} ──────────────────────────────────")

    model_path = os.path.join(MODELS_DIR, f"xgboost_{horizon}.json")
    if not os.path.exists(model_path):
        print(f"   ⚠️  Model not found: {model_path}")
        continue

    model = xgb.XGBRegressor()
    model.load_model(model_path)

    # Drop rows missing target for alignment
    df_h    = df_test[[reg_target]].dropna()
    X_test  = df_test_feat.loc[df_h.index]

    print(f"   Computing SHAP values for {len(X_test):,} test samples...")
    explainer   = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test)   # shape: (n_samples, n_features)

    # Mean absolute SHAP per feature (global importance)
    mean_abs_shap = pd.Series(
        np.abs(shap_values).mean(axis=0), index=feature_cols
    ).sort_values(ascending=False)

    print(f"\n   Top 10 features by mean |SHAP|:")
    for feat, val in mean_abs_shap.head(10).items():
        print(f"     {feat:<35} {val:.3f}")

    shap_summary_out[horizon] = mean_abs_shap.head(15).round(4).to_dict()

    # ── Summary beeswarm plot ──────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 7))
    shap.summary_plot(
        shap_values, X_test,
        feature_names=feature_cols,
        max_display=15,
        show=False,
        plot_size=None,
    )
    plt.title(f"SHAP Feature Importance — XGBoost t+{horizon[1]}", fontsize=13, pad=12)
    plt.tight_layout()
    for out_dir in [RESULTS_DIR, FIGURES_DIR]:
        plt.savefig(os.path.join(out_dir, f"fig_shap_summary_{horizon}.png"),
                    dpi=150, bbox_inches="tight")
    plt.close()
    print(f"   📊 Summary plot saved")

    # ── Waterfall plot — highest actual PM2.5 day ─────────
    y_test_vals = df_h[reg_target].values
    peak_idx    = int(np.argmax(y_test_vals))   # worst pollution day

    exp = shap.Explanation(
        values          = shap_values[peak_idx],
        base_values     = explainer.expected_value,
        data            = X_test.iloc[peak_idx].values,
        feature_names   = feature_cols,
    )

    fig, ax = plt.subplots(figsize=(10, 7))
    shap.waterfall_plot(exp, max_display=15, show=False)
    peak_date = X_test.index[peak_idx].strftime("%Y-%m-%d")
    plt.title(f"SHAP Waterfall — Peak PM2.5 Day ({peak_date}), t+{horizon[1]}", fontsize=12)
    plt.tight_layout()
    for out_dir in [RESULTS_DIR, FIGURES_DIR]:
        plt.savefig(os.path.join(out_dir, f"fig_shap_waterfall_{horizon}.png"),
                    dpi=150, bbox_inches="tight")
    plt.close()
    print(f"   📊 Waterfall plot saved  (date: {peak_date}, actual PM2.5: {y_test_vals[peak_idx]:.1f})")

# ── Save JSON ───────────────────────────────────────────────
out_path = os.path.join(RESULTS_DIR, "shap_summary.json")
with open(out_path, "w") as f:
    json.dump(shap_summary_out, f, indent=2)

print(f"\n{'='*60}")
print(f"✅  SHAP summary saved: {out_path}")
print(f"✅  Figures in 03_Data/results/ and 07_Final/report/figures/")
