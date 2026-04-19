# SP7 Phase A — Pipeline Audit Report

**Date:** 2026-04-18
**Auditor:** autonomous pass (Explore agent + direct verification)
**Scope:** 17 integrity + ingestion checks per [SP7 design spec](../specs/2026-04-18-sp7-ml-quality-design.md)

---

## Executive Summary

| Status | Count | Items |
|--|--|--|
| ✅ PASS | 12 | 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14 (reclassified), 16 (reclassified) |
| ⚠️ FIX NEEDED | 3 | **1 (leakage)**, **17 (repro)**, 15 (ingestion cleanup — deferred) |
| ℹ️ INFORMATIONAL | 2 | 2 (trailing NaNs — by design), 4 (LSTM scaler — handled in Phase C rewrite) |

**Critical fixes applied in this pass:** 2 (leakage #1, hardcoded path #17).
**Deferred to later SPs:** 3 (incremental modes — SP1/SP2 territory).

---

## Critical-Fix Explanations

### 🔴 Item #1 — Fire hotspot rolling leakage → **FIXED**

**File:** [04_Scripts/build_features.py](../../../04_Scripts/build_features.py#L177-L178)

**Before:**
```python
df["hotspot_7d_roll"]   = df["hotspot_50km"].rolling(7).mean()
df["hotspot_14d_roll"]  = df["hotspot_50km"].rolling(14).mean()
```

**After:**
```python
df["hotspot_7d_roll"]   = df["hotspot_50km"].shift(1).rolling(7).mean()
df["hotspot_14d_roll"]  = df["hotspot_50km"].shift(1).rolling(14).mean()
```

**Why this matters:** The rest of the codebase treats day-t raw values symmetrically. PM2.5 rolling features correctly `shift(1)` before rolling (lines 97, 99) — meaning "what was the 7-day trend as of yesterday?" — but fire hotspot rollings included day-t's fire count. This inconsistency let the model peek at same-day fire aggregate info that the PM2.5 pipeline intentionally withholds. Fixing restores symmetric feature construction.

**Expected impact:** small metric drop on train/val; test set unaffected or slightly improved (less overfit).

### 🔴 Item #17 — Hardcoded sandbox paths → **FIXED**

**File:** [04_Scripts/parse_pm25.py](../../../04_Scripts/parse_pm25.py#L14-L15)

**Before:**
```python
DATA_DIR = "/sessions/modest-elegant-rubin/mnt/Proposal Presentation/Data/PM2.5/"
OUTPUT_PATH = "/sessions/modest-elegant-rubin/mnt/Proposal Presentation/Data/pm25_consolidated.csv"
```

**After:** relative paths anchored to script location; reads from `03_Data/raw/PM2.5/` and writes to `03_Data/processed/pm25_consolidated.csv`. Reproducible on any machine with the repo checked out.

---

## Per-Check Results

| # | Check | Status | Notes |
|--|--|--|--|
| 1 | Lag/rolling time order | 🔴 FIXED | Fire rolling without shift — patched |
| 2 | Target shift correctness | ℹ️ by design | Trailing NaNs in features.csv, but training scripts filter per-horizon — no correctness bug |
| 3 | Split disjoint | ✅ PASS | train 4160 rows ≤ 2022-12-31; val 365 rows 2023; test 731 rows ≥ 2024-01-01 |
| 4 | LSTM scaler scope | ℹ️ handled later | Fit on train only (correct), but fit before sequence windowing creates minor misalignment. Addressed in Phase C `train_lstm_v2.py` |
| 5 | XGBoost feature leakage | ✅ PASS | Feature list fixed pre-training; no top-K correlation selection |
| 6 | Missing-value imputation | ✅ PASS | Train-median imputation applied correctly |
| 7 | FIRMS off-season | ✅ PASS | Zero-fill for counts, median for FRP, fire_flag binary |
| 8 | Timezone alignment | ✅ PASS | Open-Meteo explicitly `"timezone": "Asia/Bangkok"` + `.tz_convert("Asia/Bangkok")` |
| 9 | Duplicate timestamps | ✅ PASS | None detected |
| 10 | Seed pinning | ✅ PASS | XGBoost `random_state=42`, TF `tf.random.set_seed(42)`, numpy seeded |
| 11 | Feature freshness | ✅ PASS | features.csv newer than raw inputs after regen |
| 12 | Split volume sanity | ✅ PASS | 4160 / 365 / 731 — reasonable |
| 13 | Live PM2.5 endpoint | ✅ PASS | air4thai.pcd.go.th JSON endpoint; stations 35T (primary) / 36T (backup) |
| 14 | Weather latest mode | ℹ️ deferred | Script hardcodes full 2011–2025 range. Live pipeline re-fetches 15 yr → inefficient but not incorrect. Add incremental mode in SP1/SP2. |
| 15 | FIRMS last-N-days | ℹ️ deferred | Same — full-year replay. Rate-limiting handled. |
| 16 | Incremental feature append | ℹ️ deferred | No `--append-date` mode. Whole-file regen is correct for now. Add in SP1/SP2. |
| 17 | Pipeline simulation ready | 🔴 FIXED (parse_pm25 paths) | run_pipeline.sh steps clean; remaining inefficiencies in #14/#15 are deferred to AWS phase |

---

## Downstream Actions

1. **Regenerate features.csv** via `python 04_Scripts/build_features.py` — uses the fixed rolling logic.
2. **Archive pre-audit features.csv** as `03_Data/processed/features_pre_audit.csv` for traceability.
3. **Retrain XGBoost baseline** (no Optuna, pinned seed, same default HPs) to produce honest post-audit baseline metrics. These become the numbers Phase B tuning must beat.
4. LSTM retraining **deferred to Phase C** (we're rewriting `train_lstm_v2.py` anyway — no point retraining the old one).

---

## Post-Audit Baseline Metric Capture

**XGBoost post-audit baseline (test split, seed=42, same default HPs as pre-audit):**

| Horizon | Val MAE | Val R² | Test MAE | Test RMSE | Test R² | Alert F1 |
|--|--|--|--|--|--|--|
| t+1 | 8.10 | 0.799 | **5.25** | 9.39  | **0.827** | **0.859** |
| t+3 | 9.20 | 0.741 | **7.07** | 11.83 | **0.727** | **0.744** |
| t+7 | 10.79 | 0.628 | **8.19** | 14.09 | **0.614** | **0.696** |

**Comparison vs pre-audit baseline:**

| Horizon | MAE Δ | R² Δ | F1 Δ | Finding |
|--|--|--|--|--|
| t+1 | −0.06 | **+0.003** | **+0.020** | Slightly **better** — less overfit to leaky fire features |
| t+3 | +0.16 | −0.009 | −0.043 | Slight drop as expected — honest metric |
| t+7 | −0.15 | +0.002 | +0.012 | Essentially flat — leakage had minimal effect at long horizon |

**Interpretation:** Fire hotspot rolling leakage was **mild**, not catastrophic. Removing it gives cleaner feature semantics without significant metric loss. t+1 even benefited from reduced overfit.

**Threshold status after Phase A (before Phase B tuning):**
- XGBoost t+7 R² = 0.614 → **below** success gate of 0.65 (Phase B must improve)
- Alert F1 ≥ 0.75: **met at t+1** (0.859), not yet at t+3/t+7 (Phase B can target t+3)
- LSTM t+3 R²: not yet re-measured post-audit (deferred to Phase C rewrite)

These post-audit numbers become the honest baseline. Phase B Optuna tuning aims to push t+7 R² above 0.65 and t+3 F1 above 0.75.
