# SP7 — ML Model Quality: Design Spec

**Date:** 2026-04-18
**Owner:** Supanut Kompayak · Shuvam Shrestha
**Project:** CAAS — ChiangMai Air Quality Alert System (AT82.9002 Capstone, AIT 2026)
**Status:** Design — awaiting user review → writing-plans → implementation

---

## 1. Objective

Produce rubric-grade ML evidence (course bucket: **ML Model Development 15%**) — a tuned champion, rigorous 3-way model comparison, and a verified data pipeline — such that every claim in the eventual final report is backed by MLflow runs and JSON artifacts.

### Success Thresholds (hard gates)

- XGBoost t+7 **R² > 0.65** (currently 0.612)
- LSTM t+3 **R² > 0.65** (currently 0.540)
- At least one horizon **alert F1 ≥ 0.75** on test set

### Stopping Rule

If thresholds unreachable after 200 Optuna trials per horizon + architecture exploration in Phase C, we **document the ceiling honestly** (e.g., "deep learning underperforms tree ensembles on this 45-feature tabular time-series") rather than infinite-loop. A defensible finding is a valid outcome.

---

## 2. Four-Phase Plan

| Phase | Name | Deliverable | Blocks | Effort |
|--|--|--|--|--|
| **A** | Pipeline audit + fixes | `audit_report.md`, fixed scripts, regenerated `features.csv` if leakage found, local simulated daily run | B, C | 2–3 hrs |
| **B** | Tree tuning (parallel) | Optuna studies for XGBoost + LightGBM (≥100 trials × 3 horizons each), new champion, `xgboost_summary.json` + `lightgbm_summary.json` refreshed | D | overnight |
| **C** | LSTM rework | Architecture bakeoff + Optuna (≥50 trials × 3 horizons × top-2 variants), `lstm_v2_*` artifacts, `lstm_summary.json` refreshed | D | 1–2 days |
| **D** | Evaluation + stats | 3-way comparison, baselines, paired bootstrap significance, Scenario-C threshold refresh, ablation-NoFIRMS refresh, SHAP refresh, `model_comparison_summary.json` | — | half-day |

### Decision Points Between Phases

- **After B:** if trees meet all success thresholds → Phase C stays minimal (clean comparison only, no deep architecture rework).
- **After C:** if LSTM cannot meet t+3 R² > 0.65 → document ceiling + keep best LSTM for comparison.

---

## 3. Phase A — Pipeline Audit + Fixes

### A.1 Integrity Checks (12 items, read-only audit first)

| # | Check | File | What "good" looks like |
|--|--|--|--|
| 1 | Lag/rolling features respect time order | `04_Scripts/build_features.py` | All `.rolling()` and `.shift()` use only past values; no `center=True`, no `bfill` |
| 2 | Targets `y_t+1/3/7` correctly shifted | `04_Scripts/build_features.py` | `y_t+k = df['pm25'].shift(-k)`; last k rows dropped per split |
| 3 | Splits disjoint | `03_Data/processed/features.csv` | train ≤ 2022-12-31 < val 2023 < test ≥ 2024-01-01; no overlap, no gaps |
| 4 | Scaler fit on train only (LSTM) | `04_Scripts/train_lstm.py` | `scaler.fit(X_train)` then `transform(X_val/test)`; NOT `fit_transform(full)` |
| 5 | No feature-selection leakage | `04_Scripts/train_xgboost.py` | Feature list fixed before training; no top-K by full-y correlation |
| 6 | Missing-value imputation | `04_Scripts/build_features.py` | Documented + reproducible; `ffill` within station OK, `bfill` suspicious |
| 7 | FIRMS off-season behavior | `04_Scripts/build_features.py` | Zero-heavy features imputed sanely (0 ≠ "missing") |
| 8 | Timezone alignment | `04_Scripts/fetch_weather.py`, PCD parse | PCD ICT (UTC+7) matches Open-Meteo; all series keyed on same local date |
| 9 | Duplicate timestamps | `03_Data/processed/features.csv` | None; dedup documented if any |
| 10 | Seed pinning | all `train_*.py` | Numpy, tf, xgboost, sklearn seeds set; rerun yields identical metrics |
| 11 | Feature freshness | `features.csv` vs raw | mtime ≥ inputs; row count matches expected |
| 12 | Split volume sanity | split sizes | train ≫ val ≥ test; no near-empty split |

### A.2 Ingestion Checks (5 items, live-data readiness)

| # | Check | File | What "good" looks like |
|--|--|--|--|
| 13 | Live PM2.5 endpoint works | `04_Scripts/fetch_pm25_live.py` | Returns today's CM station value; schema matches historical |
| 14 | Weather "latest" mode | `04_Scripts/fetch_weather.py` | Supports "last N days" / "today" without full historical replay |
| 15 | FIRMS "last N days" works | `04_Scripts/fetch_firms.py` | Uses MAP_KEY; returns recent hotspots; no silent 401 |
| 16 | Incremental feature append | `04_Scripts/build_features.py` | Can append one day without full 15-year regen |
| 17 | Local scheduled-run simulation | `run_pipeline.sh` + live scripts | End-to-end: fetch → append → infer → local S3 stand-in → log; zero errors |

### A.3 Fix Policy

- Leakage or bugs found → **fix, commit with clear message, retrain before Phase B**.
- Metrics in current `03_Data/results/*.json` may shift after fixes — expected and correct.
- Archive pre-audit `features.csv` as `features_pre_audit.csv` if regeneration needed.

### A.4 Deliverables

- `audit_report.md` — 1 line per check: ✅ / ⚠️ fix needed (with diff) / ❌ blocker
- Committed fixes
- Regenerated `features.csv` (if needed)
- Local simulation log showing ingestion end-to-end

---

## 4. Phase B — Tree Tuning (XGBoost + LightGBM in parallel)

### B.1 Optuna Setup

- **Sampler:** `TPESampler` (Bayesian default)
- **Pruner:** `MedianPruner` (stop obviously bad trials early)
- **Trials per study:** 100 (bumps to 200 if thresholds missed)
- **Objective:** validation MAE on 2023 split
- **Storage:** SQLite `03_Data/results/optuna_studies/{model}_{horizon}.db` — resumable
- **MLflow:** every trial logged as nested run
- **6 studies total:** XGBoost × {t+1, t+3, t+7} + LightGBM × {t+1, t+3, t+7}

### B.2 XGBoost Search Space

```
n_estimators       ∈ int[200, 2000]   log=True
max_depth          ∈ int[3, 12]
learning_rate      ∈ float[0.005, 0.3] log=True
min_child_weight   ∈ float[0.5, 10]
subsample          ∈ float[0.5, 1.0]
colsample_bytree   ∈ float[0.5, 1.0]
reg_alpha (L1)     ∈ float[1e-4, 10]  log=True
reg_lambda (L2)    ∈ float[1e-4, 10]  log=True
```

### B.3 LightGBM Search Space

```
n_estimators       ∈ int[200, 2000]   log=True
num_leaves         ∈ int[15, 255]
max_depth          ∈ int[-1, 12]
learning_rate      ∈ float[0.005, 0.3] log=True
min_data_in_leaf   ∈ int[10, 100]
feature_fraction   ∈ float[0.5, 1.0]
bagging_fraction   ∈ float[0.5, 1.0]
reg_alpha          ∈ float[1e-4, 10]  log=True
reg_lambda         ∈ float[1e-4, 10]  log=True
```

Both use **early stopping** on val set (patience=50).

### B.4 Retrain-on-Train+Val Policy

After Optuna picks best HPs using val set, retrain on **train+val** for the final champion. Test set untouched. Standard and defensible.

### B.5 Gate Check

If XGB t+7 R² > 0.65 **AND** some alert F1 ≥ 0.75 → Phase C runs lean (comparison only, no deep rework).

### B.6 Deliverables

- New scripts: `04_Scripts/tune_xgboost.py`, `04_Scripts/tune_lightgbm.py`
- `03_Data/results/optuna_studies/*.db` (6 resumable studies)
- MLflow experiments: `CAAS-XGB-Optuna`, `CAAS-LGBM-Optuna`
- Retrained: `03_Data/models/xgboost_t{1,3,7}.json`, `03_Data/models/lightgbm_t{1,3,7}.txt`
- Refreshed: `03_Data/results/xgboost_summary.json`, new `lightgbm_summary.json`
- Optuna visualization HTML → `03_Data/results/figures/optuna/`

---

## 5. Phase C — LSTM Rework

### C.1 Root-Cause Hypotheses for Current Weakness

1. Scaler possibly fit on full series (Phase A check #4)
2. Default `seq_len` untuned
3. Shallow single-layer architecture
4. Shared model across horizons dilutes horizon-specific signal

### C.2 Architecture Exploration (5 variants, mini-bakeoff on val MAE)

| Variant | Why |
|--|--|
| **Stacked LSTM** (2–3 layers + dropout) | More capacity for long-range patterns |
| **Bidirectional LSTM** | Richer encoder representation (past-only, no leakage) |
| **LSTM + Attention** | Lets t+7 attend to specific lag windows |
| **CNN-LSTM** | 1D conv over seq_len captures short-term local patterns before recurrence |
| **Per-horizon separate models** | Horizon-specific HPs; simpler each, more total |

Pick **top-2 by val MAE**, then Optuna-tune both.

### C.3 Optuna Search Space (per variant)

```
seq_len        ∈ {7, 14, 21, 30}
hidden_units   ∈ int[32, 256]
num_layers     ∈ int[1, 3]
dropout        ∈ float[0.0, 0.5]
learning_rate  ∈ float[1e-4, 1e-2] log=True
batch_size     ∈ {32, 64, 128}
optimizer      ∈ {adam, adamw}
```

Training: early stopping on val MAE (patience=15), max 100 epochs.

### C.4 Budget Estimate (tf-metal on M4)

- ~3–5 min per LSTM run
- ≥50 trials × 3 horizons × 2 top variants = ~300 trials
- **~15–25 hrs total — plan overnight batches**
- Early-prune weak variants after ~20 trials

### C.5 Scaler Safety Rail

Enforce in code:

```python
scaler = StandardScaler()
scaler.fit(X[train_idx])
assert len(scaler.scale_) == X.shape[1]  # fit happened
X_train = scaler.transform(X[train_idx])
X_val   = scaler.transform(X[val_idx])
X_test  = scaler.transform(X[test_idx])
```

Single source of truth in `04_Scripts/train_lstm_v2.py`.

### C.6 Deliverables

- New scripts: `04_Scripts/train_lstm_v2.py`, `04_Scripts/tune_lstm.py`
- Models: `03_Data/models/lstm_v2_t{1,3,7}.keras` + `lstm_v2_scaler_t{1,3,7}.pkl`
- Refreshed: `03_Data/results/lstm_summary.json`
- MLflow experiment: `CAAS-LSTM-v2`
- Architecture ablation table: variant × horizon × val MAE

---

## 6. Phase D — Evaluation + Statistical Rigor

### D.1 Baselines (context, not competition)

| Baseline | Logic | Purpose |
|--|--|--|
| **Persistence** | ŷ_{t+k} = y_t | Floor; any real model must beat by >20% MAE |
| **Seasonal-naive** | ŷ_{t+k} = y_{t+k-365} | Captures annual PM2.5 cycle (burn season) |

### D.2 Primary Comparison Table

- **Rows:** Persistence, Seasonal-naive, XGBoost, LightGBM, LSTM-v2-best
- **Columns per horizon (t+1, t+3, t+7):**
  - Regression: MAE, RMSE, R²
  - Alert classification: Precision, Recall, F1, AUROC
  - Inference latency (ms, p50/p95, single-row input)

### D.3 Statistical Significance — Paired Bootstrap

For each (model_A vs model_B, horizon):

- Resample test predictions n=1000 with replacement
- Compute Δ(MAE) distribution, 95% CI
- **Champion claim stated only if CI doesn't cross zero**

Implementation: `04_Scripts/bootstrap_compare.py` → `model_comparison_stats.json`.

### D.4 Scenario-C Threshold Refresh

Re-run `04_Scripts/scenario_c_threshold.py` against new champion's test predictions. Update `scenario_c_summary.json`. Propagate new thresholds to `04_Scripts/serve/app.py` alert logic.

### D.5 NoFIRMS Ablation Refresh

Re-run `04_Scripts/train_xgboost_no_firms.py` with tuned champion HPs minus FIRMS block. Update `ablation_summary.json`. Tuned-vs-tuned ablation gives honest FIRMS-contribution story.

### D.6 SHAP Refresh

Re-run `04_Scripts/shap_analysis.py` on tuned XGBoost champion. Update `shap_summary.json` + figures. Note in diff-log if top-5 features change post-tuning.

### D.7 Single-Source Artifact — `model_comparison_summary.json`

Canonical file the future report + slides pull from:

```json
{
  "generated_at": "...",
  "champion": {"name": "xgboost_tuned", "version": "mlflow://..."},
  "thresholds_met": {"xgb_t7_r2_gt_065": true/false, ...},
  "per_horizon": {
    "t+1": {"models": {...}, "stats": {...}, "winner": "..."},
    "t+3": {...},
    "t+7": {...}
  },
  "baselines": {...},
  "pipeline_audit": "path/to/audit_report.md"
}
```

### D.8 Deliverables

- New scripts: `04_Scripts/bootstrap_compare.py`, `04_Scripts/generate_comparison_table.py`
- `model_comparison_summary.json`, `model_comparison_stats.json`
- Refreshed: `scenario_c_summary.json`, `ablation_summary.json`, `shap_summary.json`
- Comparison figure: `03_Data/results/figures/fig_model_comparison.png` (slide-ready)

---

## 7. Consolidated Deliverables (End of SP7)

### New Files

- `04_Scripts/tune_xgboost.py`
- `04_Scripts/tune_lightgbm.py`
- `04_Scripts/train_lstm_v2.py`
- `04_Scripts/tune_lstm.py`
- `04_Scripts/bootstrap_compare.py`
- `04_Scripts/generate_comparison_table.py`
- `audit_report.md`

### Updated Files

- `04_Scripts/build_features.py` (if audit found fixes)
- `04_Scripts/train_xgboost.py` (if audit found fixes)
- `04_Scripts/train_lstm.py` (retire in favor of `v2`)
- `04_Scripts/serve/app.py` (new alert thresholds)

### Updated Artifacts

- `03_Data/processed/features.csv` (potentially)
- `03_Data/models/xgboost_t{1,3,7}.json` (retuned champion)
- `03_Data/models/lightgbm_t{1,3,7}.txt` (new)
- `03_Data/models/lstm_v2_t{1,3,7}.keras` (new) + scalers
- `03_Data/results/{xgboost,lightgbm,lstm,ablation,scenario_c,shap}_summary.json`
- `03_Data/results/model_comparison_summary.json` (new canonical)
- `03_Data/results/model_comparison_stats.json` (new)
- `03_Data/results/optuna_studies/*.db` (6 XGB/LGBM + 6 LSTM)
- `03_Data/results/figures/fig_model_comparison.png`
- `03_Data/results/figures/optuna/*.html`

### MLflow Experiments Created

- `CAAS-XGB-Optuna`
- `CAAS-LGBM-Optuna`
- `CAAS-LSTM-v2`

---

## 8. Risks + Unknowns

| Risk | Mitigation |
|--|--|
| Audit reveals major leakage — metrics drop | Accept + document; honest metrics > inflated metrics |
| Optuna compute exceeds overnight window | Resumable SQLite studies; partial results still valid |
| LSTM can't beat tree baselines | Document ceiling finding; keep for comparison (valid outcome) |
| B thresholds unreachable | After 200 trials/horizon, doc ceiling; narrative pivots to "systematic study showed horizon difficulty" |
| New champion breaks `serve/app.py` compatibility | Version-gate via MLflow model registry alias; test pre-promotion |
| tf-metal produces non-reproducible results across platforms | Seed + document; note CPU-only replay path in Phase A appendix |

---

## 9. Links to Authoritative Sources

- Rubric: `05_Reference/final_rubric.md`
- Proposal feedback: `07_Final/FEEDBACK_FROM_PROPOSAL.md`
- Current metrics: `03_Data/results/{xgboost,lstm,ablation,scenario_c,shap,drift}_summary.json`
- Project primer: `CLAUDE.md`
- Drift policy: `05_Reference/monitoring_drift_policy_update_2026-04-03.md`

---

## 10. Next Steps After This Spec

1. User reviews this spec → changes requested OR approved
2. Lightweight brainstorm for **Frozen Deliverables Plan** (report sections × SP mapping, 14-slide outline, video storyboard, dependency matrix) → saved as `docs/superpowers/specs/2026-04-18-frozen-deliverables-plan.md`
3. Invoke **writing-plans** skill → per-file implementation plan for Phase A first
4. Execute Phase A → gate check → Phase B → gate check → Phase C → Phase D
5. Repeat brainstorm→plan→execute for remaining Track A sub-projects (SP3, SP5, SP6, SP8)
6. Track B (AWS) last: SP1 → SP2 → SP4 live runs
7. Freeze lifts → execute Frozen Deliverables Plan
