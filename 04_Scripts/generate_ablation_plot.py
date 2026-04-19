"""
CAAS — Scenario D: FIRMS Ablation Plot
Run AFTER train_xgboost_no_firms.py

Usage:
    python 04_Scripts/generate_ablation_plot.py
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE    = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(BASE, "..", "03_Data", "results")
OUTDIR  = os.path.join(BASE, "..", "01_Proposal")
BG      = "#FAFAFA"

with open(os.path.join(RESULTS, "ablation_summary.json")) as f:
    data = json.load(f)

horizons  = ["t+1", "t+3", "t+7"]
keys      = ["t1",  "t3",  "t7"]
full_mae  = [data[k]["full_mae"]      for k in keys]
nofirms_mae = [data[k]["no_firms_mae"] for k in keys]
pct_change  = [data[k]["mae_pct_change"] for k in keys]

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.patch.set_facecolor(BG)

# ── Bar chart: MAE comparison ────────────────────────────────
ax = axes[0]
x     = np.arange(3)
width = 0.32
b1 = ax.bar(x - width/2, full_mae,    width, label="Full (45 features)",   color="#2196F3", alpha=0.85)
b2 = ax.bar(x + width/2, nofirms_mae, width, label="No FIRMS (39 features)", color="#FF7043", alpha=0.85)

for bar in list(b1) + list(b2):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.08,
            f"{bar.get_height():.2f}", ha="center", va="bottom", fontsize=9.5, fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(horizons, fontsize=12)
ax.set_ylabel("MAE (µg/m³)", fontsize=10)
ax.set_title("Scenario D: FIRMS Ablation\nMAE — Full vs No-FIRMS Model", fontsize=11, fontweight="bold")
ax.legend(fontsize=9)
ax.set_facecolor(BG)
ax.spines[["top", "right"]].set_visible(False)

# ── Bar chart: % MAE change ──────────────────────────────────
ax = axes[1]
bar_colors = ["#EF5350" if p > 0 else "#4CAF50" for p in pct_change]
bars = ax.bar(horizons, pct_change, color=bar_colors, alpha=0.85, width=0.45)

for bar, val in zip(bars, pct_change):
    sign = "+" if val > 0 else ""
    ax.text(bar.get_x() + bar.get_width()/2,
            bar.get_height() + (0.1 if val >= 0 else -0.4),
            f"{sign}{val:.1f}%",
            ha="center", va="bottom", fontsize=11, fontweight="bold",
            color="#EF5350" if val > 0 else "#2E7D32")

ax.axhline(0, color="black", lw=1, alpha=0.5)
ax.set_ylabel("MAE Change vs Full Model (%)", fontsize=10)
ax.set_title("FIRMS Feature Contribution\n(+% = worse without FIRMS)", fontsize=11, fontweight="bold")
ax.set_facecolor(BG)
ax.spines[["top", "right"]].set_visible(False)
ax.tick_params(axis="x", labelsize=12)

fig.suptitle(
    "Scenario D: NASA FIRMS Fire Hotspot Ablation Study\n"
    "XGBoost Test Set Performance (2024–2025)",
    fontsize=13, fontweight="bold"
)
plt.tight_layout()
out = os.path.join(OUTDIR, "fig_firms_ablation.png")
plt.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
plt.close()
print(f"✅  Saved: {out}")
print("\n🎉  All plots ready — tell Claude to insert into report!")
