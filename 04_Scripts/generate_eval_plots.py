"""
CAAS — Evaluation Plots
Generates:
  1. Alert confusion matrix (XGBoost, all 3 horizons)
  2. Haze season vs non-haze MAE breakdown

Run from project root:
    python 04_Scripts/generate_eval_plots.py
"""

import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

BASE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "03_Data", "results")
OUTDIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "01_Proposal")
os.makedirs(OUTDIR, exist_ok=True)

BG = "#FAFAFA"
COLORS = {"t+1": "#2196F3", "t+3": "#FF9800", "t+7": "#4CAF50"}
HAZE_MONTHS = [1, 2, 3, 4]   # Jan–Apr = haze season

horizons = {"t+1": "t1", "t+3": "t3", "t+7": "t7"}

# ════════════════════════════════════════════════════════════
# PLOT 1 — Alert Confusion Matrix (3 horizons side by side)
# ════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
fig.patch.set_facecolor(BG)

for ax, (label, key) in zip(axes, horizons.items()):
    df = pd.read_csv(os.path.join(BASE, f"xgboost_{key}_test_predictions.csv"),
                     parse_dates=["date"])

    y_true = df["alert_actual"].astype(int).values
    y_pred = df["alert_predicted"].astype(int).values

    # Confusion matrix values
    TP = int(((y_true == 1) & (y_pred == 1)).sum())
    TN = int(((y_true == 0) & (y_pred == 0)).sum())
    FP = int(((y_true == 0) & (y_pred == 1)).sum())
    FN = int(((y_true == 1) & (y_pred == 0)).sum())

    cm = np.array([[TN, FP], [FN, TP]])
    total = cm.sum()

    precision = TP / (TP + FP) if (TP + FP) > 0 else 0
    recall    = TP / (TP + FN) if (TP + FN) > 0 else 0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    # Plot heatmap manually
    cmap = plt.cm.Blues
    im = ax.imshow(cm, cmap=cmap, vmin=0, vmax=total * 0.6)

    labels = [["TN", "FP"], ["FN", "TP"]]
    for i in range(2):
        for j in range(2):
            val = cm[i, j]
            pct = val / total * 100
            color = "white" if val > total * 0.3 else "#212121"
            ax.text(j, i, f"{labels[i][j]}\n{val}\n({pct:.1f}%)",
                    ha="center", va="center", fontsize=11,
                    fontweight="bold", color=color)

    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Pred: Safe", "Pred: Alert"], fontsize=9)
    ax.set_yticklabels(["Act: Safe", "Act: Alert"], fontsize=9)
    ax.set_title(
        f"Horizon {label}\n"
        f"Precision={precision:.3f}  Recall={recall:.3f}  F1={f1:.3f}",
        fontsize=10, fontweight="bold", pad=8
    )
    ax.set_facecolor(BG)

fig.suptitle(
    "XGBoost Alert Classification — Confusion Matrix (Test Set 2024–2025)\n"
    "Alert threshold: PM2.5 > 50 µg/m³",
    fontsize=13, fontweight="bold", y=1.03
)
plt.tight_layout()
out1 = os.path.join(OUTDIR, "fig_confusion_matrix.png")
plt.savefig(out1, dpi=180, bbox_inches="tight", facecolor=BG)
plt.close()
print(f"✅  Saved: {out1}")


# ════════════════════════════════════════════════════════════
# PLOT 2 — Haze Season vs Non-Haze MAE Breakdown
# ════════════════════════════════════════════════════════════
records = []
for label, key in horizons.items():
    df = pd.read_csv(os.path.join(BASE, f"xgboost_{key}_test_predictions.csv"),
                     parse_dates=["date"])
    df["is_haze"] = df["date"].dt.month.isin(HAZE_MONTHS)
    df["abs_err"] = (df["actual"] - df["predicted"]).abs()

    for season, mask in [("Haze (Jan–Apr)", df["is_haze"]),
                         ("Non-Haze (May–Dec)", ~df["is_haze"])]:
        sub = df[mask]
        records.append({
            "horizon": label,
            "season":  season,
            "mae":     sub["abs_err"].mean(),
            "rmse":    np.sqrt((sub["abs_err"]**2).mean()),
            "n":       len(sub),
        })

res = pd.DataFrame(records)

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.patch.set_facecolor(BG)

# Grouped bar — MAE
ax = axes[0]
width = 0.32
x     = np.arange(3)
h_vals    = res[res["season"].str.startswith("Haze")]["mae"].values
nh_vals   = res[res["season"].str.startswith("Non")]["mae"].values
b1 = ax.bar(x - width/2, h_vals,  width, label="Haze (Jan–Apr)",    color="#EF5350", alpha=0.85)
b2 = ax.bar(x + width/2, nh_vals, width, label="Non-Haze (May–Dec)", color="#42A5F5", alpha=0.85)

for bar in list(b1) + list(b2):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.15,
            f"{bar.get_height():.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

# Persistence reference lines
persistence = {"t+1": 10.42, "t+3": 18.51, "t+7": 22.66}
for i, (hl, _) in enumerate(horizons.items()):
    ax.plot([i - 0.4, i + 0.4], [persistence[hl]] * 2,
            "k--", lw=1.2, alpha=0.5)

ax.set_xticks(x)
ax.set_xticklabels(list(horizons.keys()), fontsize=11)
ax.set_ylabel("MAE (µg/m³)", fontsize=10)
ax.set_title("MAE by Season\n(dashed = persistence baseline)", fontsize=11, fontweight="bold")
ax.legend(fontsize=9)
ax.set_facecolor(BG)
ax.spines[["top", "right"]].set_visible(False)

# Grouped bar — RMSE
ax = axes[1]
h_rmse  = res[res["season"].str.startswith("Haze")]["rmse"].values
nh_rmse = res[res["season"].str.startswith("Non")]["rmse"].values
b3 = ax.bar(x - width/2, h_rmse,  width, label="Haze (Jan–Apr)",    color="#EF5350", alpha=0.85)
b4 = ax.bar(x + width/2, nh_rmse, width, label="Non-Haze (May–Dec)", color="#42A5F5", alpha=0.85)

for bar in list(b3) + list(b4):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.15,
            f"{bar.get_height():.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(list(horizons.keys()), fontsize=11)
ax.set_ylabel("RMSE (µg/m³)", fontsize=10)
ax.set_title("RMSE by Season", fontsize=11, fontweight="bold")
ax.legend(fontsize=9)
ax.set_facecolor(BG)
ax.spines[["top", "right"]].set_visible(False)

# Sample sizes annotation
n_haze = res[res["season"].str.startswith("Haze")]["n"].values
n_non  = res[res["season"].str.startswith("Non")]["n"].values
fig.text(0.5, -0.04,
         f"Sample sizes — Haze: {n_haze[0]} days | Non-Haze: {n_non[0]} days (test set 2024–2025)",
         ha="center", fontsize=9, color="#555")

fig.suptitle("XGBoost Performance: Haze Season vs Non-Haze Season",
             fontsize=13, fontweight="bold")
plt.tight_layout()
out2 = os.path.join(OUTDIR, "fig_haze_breakdown.png")
plt.savefig(out2, dpi=180, bbox_inches="tight", facecolor=BG)
plt.close()
print(f"✅  Saved: {out2}")
print("\nDone — Step 1 complete.")
