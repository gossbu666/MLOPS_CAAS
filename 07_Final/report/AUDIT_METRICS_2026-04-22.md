# Report Metrics Audit — 2026-04-22

Compares `07_Final/report/final_report_CAAS.pdf` (compiled 2026-04-17) against the current `03_Data/results/*.json` ground truth. Use this to steer the final-report refresh.

---

## 🔴 Critical — change story, not just numbers

### 1. Champion framing is out of date

| | Report PDF | Current MLflow + serve/app.py |
|--|--|--|
| Champion | XGBoost | **LightGBM** (Optuna-tuned) |
| Fallback | LSTM (comparison) | **XGBoost** (+ LSTM tuned for comparison) |

The report never mentions LightGBM. Needs introduction in §3.4, Executive Summary, and §4 (MLflow experiment list — reference `CAAS-LGBM-Optuna`).

### 2. XGBoost numbers in §3.4.1 / §B.1 are from an older training run

| Horizon | Report Test MAE | Current `xgboost_summary.json` | Report Test R² | Current R² |
|--|--|--|--|--|
| t+1 | 5.31 | 5.307 | 0.824 | **0.843** |
| t+3 | 6.91 | **7.081** | 0.736 | **0.723** |
| t+7 | 8.34 | **8.897** | 0.612 | **0.544** |

t+7 got noticeably **worse** after retraining (R² 0.612 → 0.544, AUROC 0.959 → 0.933). This is a real regression, not just rounding.

### 3. Alert F1 table §B.3 — same issue at t+3/t+7

| Horizon | Report F1 | JSON F1 |
|--|--|--|
| t+1 | 0.839 | 0.844 |
| t+3 | **0.787** | **0.723** |
| t+7 | **0.684** | **0.584** |

---

## 🟡 Needs refresh but low surprise

### 4. Scenario D (FIRMS ablation) — pct change matches, absolute MAE doesn't

Report Table 3.5 cites "Full MAE 5.31/6.91/8.34" (from old Table 3.3) with no-FIRMS "5.67/7.27/8.70". Current `ablation_summary.json` has its own pair: full `6.108/7.373/8.441` vs no-FIRMS `6.522/7.749/8.802`. The MAE **% increase matches** (6.78/5.1/4.28 → report says 6.8/5.1/4.3), so the contribution story stands — but the absolute numbers should come from the JSON, not from the champion table.

### 5. Scenario C threshold analysis — ✅ matches

Report §3.6 says t+1 optimal threshold 53.7 µg/m³ and +4.0% F1 gain. JSON: optimal 53.72, f1_gain 0.0399. No change needed.

### 6. SHAP top-5 features table §B.4 — spot-check later

Not re-verified against `shap_summary.json` in this audit. Cross-check when refreshing.

---

## 🟢 Clean — already aligned

- LSTM baseline test metrics (Table 3.4, B.2) match `lstm_summary.json` exactly.
- Alert-F1 at t+1 (0.839) is within rounding of current JSON (0.844).
- Section structure, the 7-section rubric layout, MLflow/FastAPI/EC2/Docker narrative.

---

## Recommended edits (in order)

1. **§1 Executive Summary + §3.4**: promote LightGBM-Optuna to champion; demote XGBoost to "strong secondary / fallback"; add LSTM-tuned (Optuna) to comparison set.
2. **Table 3.3 → LightGBM Test**: MAE 5.12/6.77/8.25, RMSE 9.00/11.78/14.36, R² 0.841/0.729/0.600, AUROC 0.992/0.973/0.946.
3. **Table B.1 → merge XGBoost + LightGBM val/test** or split into two tables.
4. **Table B.3**: regenerate alert metrics for the NEW champion (LightGBM) @ 50 µg/m³: F1 0.852/0.747/0.713.
5. **§3.5 Scenario D**: rebase table on `ablation_summary.json` absolute MAE (6.108 vs 6.522, etc.) — keep the 6.8/5.1/4.3% message.
6. **§4 MLflow narrative**: rename experiments to current names (`CAAS-LGBM-Optuna`, `CAAS-XGB-Optuna`, `CAAS-LSTM-Tuning`, `CAAS-Ablation-NoFIRMS`) — 8 experiments total.
7. **Reference to serve/app.py**: champion = LightGBM, fallback = XGBoost; `/forecast` now has 5-min TTL cache.

---

## What's still fine to say untouched

- "MAE improves +23% at t+3, +24% at t+7 over persistence baseline" — recompute against new champion before rewriting, but the magnitude likely survives.
- Cost/day story, Terraform IaC narrative, CI/CD workflow description.
- FIRMS fire-contribution framing (5-7% MAE cost when removed).
