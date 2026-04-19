"""
CAAS — Scenario C: Precision-Recall Threshold Analysis
Finds the F1-maximising alert threshold for each XGBoost horizon.

Default threshold = 50 µg/m³ (WHO/Thai standard).
This script explores whether a different threshold improves the alert classifier.

Outputs:
  03_Data/results/scenario_c_summary.json   — optimal thresholds + metrics
  03_Data/results/fig_pr_curve_t1.png       — PR curve t+1
  03_Data/results/fig_pr_curve_t3.png       — PR curve t+3
  03_Data/results/fig_pr_curve_t7.png       — PR curve t+7

Usage:
    python scenario_c_threshold.py
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import (
    precision_recall_curve, f1_score, precision_score,
    recall_score, roc_auc_score, average_precision_score
)

# ── Paths ───────────────────────────────────────────────────
BASE        = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE, "..", "03_Data", "results")
FIGURES_DIR = os.path.join(BASE, "..", "07_Final", "report", "figures")
os.makedirs(FIGURES_DIR, exist_ok=True)

HORIZONS       = ["t1", "t3", "t7"]
DEFAULT_THRESH = 50.0

summary = {}

print("=" * 60)
print("  CAAS — Scenario C: Threshold Analysis")
print("=" * 60)

for horizon in HORIZONS:
    pred_path = os.path.join(RESULTS_DIR, f"xgboost_{horizon}_test_predictions.csv")
    if not os.path.exists(pred_path):
        print(f"\n⚠️  Skipping {horizon} — predictions file not found")
        continue

    df = pd.read_csv(pred_path)
    y_true   = df["alert_actual"].values
    y_scores = df["predicted"].values   # raw PM2.5 predicted values as score

    print(f"\n── Horizon {horizon.upper()} ──────────────────────────────────")
    print(f"   Total samples: {len(y_true):,}  |  Positives (alert days): {y_true.sum():,}")

    # ── Precision-Recall curve ─────────────────────────────
    precision_arr, recall_arr, thresholds = precision_recall_curve(y_true, y_scores)
    ap_score = average_precision_score(y_true, y_scores)

    # F1 at each threshold
    # precision_recall_curve returns one extra point (threshold-less) — align
    f1_arr = np.where(
        (precision_arr[:-1] + recall_arr[:-1]) > 0,
        2 * precision_arr[:-1] * recall_arr[:-1] / (precision_arr[:-1] + recall_arr[:-1]),
        0.0
    )

    best_idx       = np.argmax(f1_arr)
    best_threshold = thresholds[best_idx]
    best_f1        = f1_arr[best_idx]
    best_precision = precision_arr[best_idx]
    best_recall    = recall_arr[best_idx]

    # Metrics at default threshold (50 µg/m³)
    pred_default = (y_scores > DEFAULT_THRESH).astype(int)
    default_f1        = f1_score(y_true, pred_default, zero_division=0)
    default_precision = precision_score(y_true, pred_default, zero_division=0)
    default_recall    = recall_score(y_true, pred_default, zero_division=0)

    auroc = roc_auc_score(y_true, y_scores)

    print(f"\n   Default threshold (50 µg/m³):")
    print(f"     Precision: {default_precision:.3f}  Recall: {default_recall:.3f}  F1: {default_f1:.3f}")
    print(f"\n   Optimal threshold ({best_threshold:.1f} µg/m³):")
    print(f"     Precision: {best_precision:.3f}  Recall: {best_recall:.3f}  F1: {best_f1:.3f}")
    print(f"\n   AUROC: {auroc:.4f}  |  AP: {ap_score:.4f}")
    print(f"   F1 gain from optimal threshold: {best_f1 - default_f1:+.3f}")

    summary[horizon] = {
        "n_samples":          int(len(y_true)),
        "n_alert_days":       int(y_true.sum()),
        "auroc":              round(auroc, 4),
        "average_precision":  round(ap_score, 4),
        "default_threshold":  DEFAULT_THRESH,
        "default_precision":  round(default_precision, 4),
        "default_recall":     round(default_recall, 4),
        "default_f1":         round(default_f1, 4),
        "optimal_threshold":  round(float(best_threshold), 2),
        "optimal_precision":  round(float(best_precision), 4),
        "optimal_recall":     round(float(best_recall), 4),
        "optimal_f1":         round(float(best_f1), 4),
        "f1_gain":            round(float(best_f1 - default_f1), 4),
    }

    # ── Plot ───────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(f"Scenario C — Alert Classifier Analysis (t+{horizon[1]})", fontsize=13)

    # Left: PR curve
    ax = axes[0]
    ax.plot(recall_arr, precision_arr, lw=2, color="#2196F3",
            label=f"PR curve (AP={ap_score:.3f})")
    # Mark default threshold point
    ax.scatter([default_recall], [default_precision], color="orange", s=100, zorder=5,
               label=f"Default 50 µg/m³ (F1={default_f1:.3f})")
    # Mark optimal threshold point
    ax.scatter([best_recall], [best_precision], color="red", s=120, marker="*", zorder=6,
               label=f"Optimal {best_threshold:.0f} µg/m³ (F1={best_f1:.3f})")
    ax.set_xlabel("Recall", fontsize=11)
    ax.set_ylabel("Precision", fontsize=11)
    ax.set_xlim(0, 1.05)
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=9)
    ax.set_title("Precision-Recall Curve")
    ax.grid(True, alpha=0.3)

    # Right: F1 vs threshold
    ax2 = axes[1]
    ax2.plot(thresholds, f1_arr, lw=2, color="#4CAF50", label="F1 score")
    ax2.axvline(DEFAULT_THRESH, color="orange", linestyle="--", lw=1.5,
                label=f"Default 50 µg/m³ (F1={default_f1:.3f})")
    ax2.axvline(best_threshold, color="red", linestyle="--", lw=1.5,
                label=f"Optimal {best_threshold:.0f} µg/m³ (F1={best_f1:.3f})")
    ax2.set_xlabel("Threshold (µg/m³)", fontsize=11)
    ax2.set_ylabel("F1 Score", fontsize=11)
    ax2.legend(fontsize=9)
    ax2.set_title("F1 Score vs Alert Threshold")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    # Save to both results and 07_Final figures
    for out_dir in [RESULTS_DIR, FIGURES_DIR]:
        fig_path = os.path.join(out_dir, f"fig_pr_curve_{horizon}.png")
        plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"   📊 Figures saved")

# ── Save summary JSON ───────────────────────────────────────
out_path = os.path.join(RESULTS_DIR, "scenario_c_summary.json")
with open(out_path, "w") as f:
    json.dump(summary, f, indent=2)
print(f"\n{'='*60}")
print(f"✅  Scenario C summary saved: {out_path}")
print(f"✅  Figures saved to 03_Data/results/ and 07_Final/report/figures/")
