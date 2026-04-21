# CAAS Project — Handoff Status Log
**Last updated:** 2026-04-21 (session 5 — CI/CD live-green)
**Updated by:** Claude
**Project:** ChiangMai Air Quality Alert System — End-to-End MLOps Pipeline
**Course:** AT82.9002 Data Engineering and MLOps, AIT
**Students:** Supanut Kompayak (st126055) · Shuvam Shrestha (st125975)
**Presentation deadline:** 2026-04-24

---

## Session 5 (2026-04-21) — CI/CD live-green

### Triggered by
Recurring GitHub Actions failure emails (daily_pipeline every 3h + drift_check daily + tests on push). Grader opening Actions tab would have seen red ❌ everywhere = bad MLOps signal.

### Root causes fixed (in order discovered)

1. **No GitHub Secrets set** — workflows referenced `secrets.AWS_*` + `secrets.FIRMS_MAP_KEY` but they weren't configured. Set 5 secrets via `gh secret set`:
   - `FIRMS_MAP_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION=ap-southeast-1`, `S3_BUCKET_NAME=caas-mlops-st126055`
   - Note: local `.env` has stale `S3_BUCKET_NAME=caas-data-bucket` — GH Secret is correct, `.env` out of sync (not critical for live EC2 which uses IAM role).

2. **pip `resolution-too-deep`** — pip's resolver choked on requirements.txt dependency graph (evidently + tensorflow + xgboost + many transitive pins like openmeteo-sdk, narwhals, nltk versions). All 3 workflows (test, daily_pipeline, drift_check) died at install step.
   - Fix: migrated to `uv` via `astral-sh/setup-uv@v4`. Install time dropped from ~6 min (pip retrying depth) to ~40s.
   - Required `cache-dependency-glob: requirements.txt` in setup-uv config (default looks for uv.lock which we don't have).
   - Commit: `4f34c2e` + `270b458`.

3. **Evidently script `TypeError: bool_ not JSON serializable`** — when drift detected, `evidently_report.py` POSTs to GitHub API with `psi_drift`, `ks_drift`, `mae_flag` which are numpy `bool_` values. `requests.post(json=...)` calls `json.dumps(allow_nan=False)` which doesn't handle numpy types.
   - Fix: cast to Python `bool()` before building payload in `04_Scripts/monitoring/evidently_report.py` line 277–279.

4. **Drift S3 upload path mismatch** — workflow did `aws s3 sync 03_Data/results/drift_reports/` but script saves HTML flat to `03_Data/results/drift_report_YYYYMMDD.html`. Directory didn't exist → exit 255.
   - Fix: upload `drift_summary.json` to stable S3 path (dashboard reads this) + loop over `drift_report_*.html` files for archive.
   - Commit: `62c29c9`.

5. **`.claude/scheduled_tasks.lock` accidentally committed** — Claude Code auto-memory lockfile slipped into `git add -A`.
   - Fix: `git rm --cached` + added `.claude/` to `.gitignore`. Commit: `d00ccc8`.

### Final workflow status (2026-04-21 11:15 Bangkok)

| Workflow | Trigger | Status | Run time |
|---|---|---|---|
| `test.yml` | push to main/develop | ✅ success | 42s |
| `drift_check.yml` | daily 23:00 UTC + dispatch | ✅ success | 1m4s |
| `daily_pipeline.yml` | every 3h + dispatch | ⏳ running (~20 min — FIRMS fetch slow) | TBD |
| `retrain.yml` | annual Dec 1 | ⏸ idle (won't fire before presentation) | — |

Pipeline in-flight at write time. Past steps all green: Install deps (uv), PM2.5 fetch, weather fetch. Currently on FIRMS hotspot fetch (NASA API can be slow — legitimate work, not a hang).

### Files changed this session
- `.github/workflows/daily_pipeline.yml` — pip→uv
- `.github/workflows/drift_check.yml` — pip→uv + S3 upload path fix
- `.github/workflows/test.yml` — pip→uv + ruff install via uv
- `04_Scripts/monitoring/evidently_report.py` — `bool()` cast for numpy types
- `.gitignore` — add `.claude/`

### Outstanding work (unchanged from session 4)
1. **PPTX slides** — still 0/14, outline only
2. **Demo video** — `07_Final/video/` still empty
3. **Final report metric refresh** — LightGBM champion + FIRMS contribution narrative
4. **Dashboard screenshots** for slides/report
5. **`FINALSUBMIT/` cleanup** — contains PROPOSAL PDFs from March
6. **`terraform destroy`** — after 2026-04-24 presentation

---

## Session 4 (2026-04-20 → 2026-04-21) — AWS deploy + Dashboard v2

### Live infrastructure (running)
- **EC2 t3.small** in ap-southeast-1 at `54.255.152.224` (Free Tier account)
- **S3 bucket** `caas-mlops-st126055` (84 objects, ~100 MB — models, processed data, results, drift reports)
- **IAM role** `caas-ec2-role` + instance profile (S3 least-privilege: Get/Put/List only, no Delete)
- **SSH keypair** `caas-key` (local at `~/.ssh/caas-key.pem`, locked to IP `27.145.5.100/32`)
- Terraform state: local only (`infra/.terraform/`, gitignored)
- Cost: ~$0.50/day — keep running until 2026-04-24, then `terraform destroy`

### Live URLs
| Service | URL | Notes |
|--|--|--|
| FastAPI | http://54.255.152.224:8000 | LightGBM champion + XGBoost fallback via `?model=` |
| FastAPI docs | http://54.255.152.224:8000/docs | OpenAPI auto-docs |
| Streamlit dashboard | http://54.255.152.224:8502 | Two-tab: Public View + Model Insights |
| MLflow UI | http://54.255.152.224:5001 | Tracking backend on `./mlruns` volume |

### Docker stack (running on EC2 via `docker compose up --build -d`)
- `caas-api` — FastAPI uvicorn, 2 workers, port 8000 (healthy)
- `caas-dashboard` — Streamlit (reuses api image), port 8502→8501
- `caas-mlflow` — MLflow server (separate minimal image `Dockerfile.mlflow`), port 5001→5000

Port mapping notes:
- Dashboard external `8502` chosen to avoid local Streamlit conflicts on dev machines
- MLflow external `5001` chosen to avoid macOS AirPlay on port 5000
- Same mapping used on EC2 for consistency

### Serving layer (champion-first)
- [`04_Scripts/serve/app.py`](../04_Scripts/serve/app.py) serves **LightGBM as champion** + **XGBoost as A/B fallback** via `?model=lightgbm|xgboost` query param.
- `/health`, `/forecast`, `/history`, `/model/info`, `/predict` — all 5 endpoints validated on production EC2.
- [`Dockerfile`](../Dockerfile) runtime stage adds `libgomp1` for LightGBM OpenMP; non-root user `caas`; healthcheck on `/health`.

### Dashboard v2 — two-tab redesign ([`04_Scripts/serve/dashboard.py`](../04_Scripts/serve/dashboard.py))
- **Sidebar** (persistent): station, last data date, champion badge, refresh button, about block
- **Tab 1: Public View**
  - Context-aware alert banner (red if any horizon ≥ 50 µg/m³, orange if ≥ 25, green otherwise)
  - 3 minimal forecast cards with left-border accent (no heavy cards, no gradients)
  - **Combined chart**: 60-day observed history + 3 forecast diamonds connected by dashed line + Thai/hazard threshold rules
  - Health guidance text driven by worst horizon
  - AQI level reference (collapsible)
- **Tab 2: Model Insights**
  - Radio: LightGBM (champion) / XGBoost (fallback)
  - Side-by-side prediction table with Δ column (LGBM − XGB)
  - Test metrics (MAE / RMSE / R² / Alert F1 / AUROC) per horizon for selected model
  - **Drift status** (reads `s3://caas-mlops-st126055/results/drift_summary.json` via EC2 IAM role) — 4 top-line metrics (generated date, core/soft drift counts, retrain flag) + per-feature table (PSI / KS / traffic-light status)
  - **FIRMS contribution chart** — summed XGBoost gain of all hotspot/fire features at t+1 / t+3 / t+7, showing biomass-burning signal rises with horizon
  - Top-10 feature importance bar chart (horizon selector)

### FIRMS verification (asked 2026-04-21)
All 6 production models (LGBM + XGB × t+1/t+3/t+7) use **6 FIRMS features**: `hotspot_50km`, `hotspot_100km`, `hotspot_7d_roll`, `hotspot_14d_roll`, `fire_flag`, `roll7_x_fire`.

Contribution share (summed XGBoost gain):
| Horizon | FIRMS share | Top FIRMS feature |
|--|:-:|--|
| t+1 | ~4% | `hotspot_7d_roll` (#5) |
| t+3 | ~7% | `hotspot_7d_roll` (#4) |
| t+7 | ~12% | `hotspot_7d_roll` (#3) |

Inference uses real FIRMS values (not zeros) — 14/30 recent days have `hotspot_100km > 0`. Dec 2025 hotspot counts are low because it's off-season; Feb-Apr (current) is peak haze season so live inference would show stronger fire signal.

### Infrastructure files
- [`infra/main.tf`](../infra/main.tf) — S3 + IAM + SG + EC2 (security group description ASCII-only — hit AWS validation on em-dash)
- [`infra/variables.tf`](../infra/variables.tf) — defaults: `t3.small`, `ap-southeast-1`, bucket `caas-mlops-st126055`, dashboard port 8502, mlflow port 5001
- [`infra/outputs.tf`](../infra/outputs.tf) — all URLs computed from variables; includes `dashboard_url` + `github_secrets_summary`
- `infra/terraform.tfvars` (gitignored) — SSH locked to user's IPv4 `/32`
- [`docker-compose.yml`](../docker-compose.yml) — 3 services; dashboard container gets `S3_BUCKET_NAME` + `AWS_REGION` env passthroughs so boto3 (via IAM role) can fetch drift/importance from S3
- EC2 `user_data` clones `https://github.com/gossbu666/MLOPS_CAAS.git`, installs Docker via official script, `aws s3 sync` (fail-soft) to pull models/data, then `docker compose up --build -d`

### Repo hygiene
- GitHub repo: `https://github.com/gossbu666/MLOPS_CAAS` (public)
- `.gitignore` excludes: `.env`, `caas-env/`, `mlruns/`, `03_Data/raw/`, `*.keras`, `*.pkl`, `infra/.terraform*`, `infra/terraform.tfvars`, `infra/terraform.tfstate*`
- 175 files committed; `.env` verified not in git
- LightGBM models (`.txt`) + XGBoost models (`.json`) ARE in git (fit under GitHub size limits)
- LSTM models (`.keras`) + scalers (`.pkl`) NOT in git — pulled from S3 at EC2 boot

### Pending for 2026-04-24 presentation
1. **Final report PDF refresh** — `07_Final/report/final_report_CAAS.pdf` still references old champion (XGBoost). Must update metrics + add FIRMS contribution finding. **Do LAST** after code/infra freeze.
2. **PPTX slides** — `07_Final/slides/SLIDES_OUTLINE.md` exists, no `.pptx` yet. 14 slides planned.
3. **Demo video** — `07_Final/video/` empty. ~10 min recording of live dashboard + MLflow + drift story.
4. **Optional**: set GitHub Secrets (`AWS_*`, `S3_BUCKET_NAME`, `FIRMS_MAP_KEY`) to enable `daily_pipeline.yml` auto-drift every 3 hours.

### Post-presentation cleanup
```bash
cd "/Users/supanut.k/WORKING_DRIVE/AIT/2nd_semester/DATA ENGINEER/Proposal Presentation/infra"
terraform destroy       # tears down EC2 + SG + IAM (S3 bucket emptied via force_destroy=true)
```

### Known gotchas (if resuming work)
- EC2 uses `docker compose up --build` at boot — rebuild takes ~3-5 min on t3.small
- Docker healthcheck for `caas-dashboard` inherits from api image (checks port 8000) → container shows `unhealthy` but is actually fine on 8501
- `st.button/st.dataframe width="stretch"` doesn't work on Streamlit 1.37.1 — use `use_container_width=True`
- `drift_summary.json` "features" key is a **list of dicts**, not a dict keyed by feature name — dashboard parser accounts for this
- Rebuild after dashboard change: `ssh ... 'cd /home/ubuntu/caas && sudo git pull && sudo docker compose up -d --build dashboard'`

---

## Session 3 (2026-04-18) — SP7 ML-quality pass

### Phase A — Audit + fixes
- **Fire-hotspot rolling leakage fixed** in [`04_Scripts/build_features.py`](../04_Scripts/build_features.py#L177-L178): added `.shift(1)` so hotspot 7d/14d rollings are symmetric with pm25 rollings (they looked at day-t, which peeked at fire aggregate the pm25 pipeline was intentionally withholding).
- **Hardcoded sandbox paths fixed** in [`04_Scripts/parse_pm25.py`](../04_Scripts/parse_pm25.py#L14-L17) — now uses relative paths anchored to the script file.
- Archived pre-audit features as `03_Data/processed/features_pre_audit.csv`; regenerated `features.csv`.
- Honest post-audit XGBoost baseline captured (slight drop on val, essentially flat on test — confirming the leakage was mild).
- Full report: [`docs/superpowers/artifacts/2026-04-18-phase-a-audit-report.md`](../docs/superpowers/artifacts/2026-04-18-phase-a-audit-report.md)

### Phase B — Tree-model tuning (100 Optuna trials × 3 horizons, each model)
- `04_Scripts/tune_xgboost.py` — 8-dim search, resumable SQLite, MLflow nested runs
- `04_Scripts/tune_lightgbm.py` — parallel LGBM tuner
- Studies at `03_Data/results/optuna_studies/{xgb,lgbm}_t{1,3,7}.db`
- **Important finding: XGBoost Optuna overfit the 2023 validation set at t+7.** Test R² dropped 0.614 → 0.544 after 100 trials. LightGBM tuning stayed honest (test R² 0.600 at t+7).

### Phase C — LSTM rewrite + tuning
- [`04_Scripts/train_lstm_v2.py`](../04_Scripts/train_lstm_v2.py) — pluggable architectures (stacked / bidirectional / attention / cnn_lstm), **continuous sequence windowing** (no longer loses first `seq_len` rows of each split), **scaler hygiene with assert guard**.
- [`04_Scripts/tune_lstm.py`](../04_Scripts/tune_lstm.py) — 30 Optuna trials per horizon over arch + seq_len + 5 HPs.
- Had to pin `numpy<2` (TF 2.17 incompatible with numpy 2.4.4 that Optuna install pulled).
- Best v2 architectures picked by Optuna: attention (t+1), cnn_lstm (t+3), bidirectional (t+7).
- v2 is ON PAR with v1 — better at t+3 (R² 0.540 → 0.571) but worse at t+7 (0.608 → 0.503).

### Phase D — Statistical comparison
- [`04_Scripts/bootstrap_compare.py`](../04_Scripts/bootstrap_compare.py) — paired bootstrap n=5000, 95% CI on Δ MAE, pairwise between all 4 ML models.
- [`04_Scripts/generate_comparison_table.py`](../04_Scripts/generate_comparison_table.py) — adds **persistence** and **seasonal-7** naive baselines.
- Results: `03_Data/results/bootstrap_compare.json`, `comparison_table.md`, `comparison_table.json`.

### Champion recommendation (post-SP7)

| Horizon | Recommended champion | Why |
|--|--|--|
| t+1 | **LightGBM** (MAE 5.12, F1 0.852) | ties XGB on MAE, wins F1. Persistence technically wins MAE (4.46) but only ties F1 — models win on precision/recall trade-off |
| t+3 | **LightGBM** (MAE 6.77, F1 0.747) | significantly beats XGBoost (CI +0.08 to +0.56) and beats LSTM v1 by ~2 MAE points |
| t+7 | **LightGBM or LSTM v1** (MAE 8.25 / 8.06, F1 0.713 / 0.694) | statistically indistinguishable (CI crosses 0). Use LightGBM — faster inference |

**SP7 success-gate status:**
- ✅ Alert F1 ≥ 0.75 on at least one horizon (LGBM t+1 0.852; LGBM t+3 0.747)
- ❌ XGB t+7 R² > 0.65 — best we got was LGBM 0.600 (XGB tuned 0.544)
- ❌ LSTM t+3 R² > 0.65 — best was v2 0.571

**Interpretation:** the 0.65 R² gate for t+7 is likely a dataset-hardness ceiling, not a tuning failure. Seasonal-7 naive hits 0.377 and persistence 0.377, so our models are adding ~0.2 R² of real predictive lift — but three-day-ahead atmospheric prediction from local sensors has inherent noise floors.

### Honest-framing finding
Naive persistence MAE 4.46 **beats every model** at t+1 (MAE 5.12–6.79) — because 24-hour air quality is dominated by short-term autocorrelation. Models add defensible value at t+3 and t+7 only. The final report should frame t+1 forecasting as "validation that the model is competitive with the hard-to-beat autocorrelation floor," not as a headline win.

---

---

## Quick Summary

End-to-end MLOps system that forecasts PM2.5 air quality in Chiang Mai 1/3/7 days ahead.
**Final report is DONE** — `07_Final/report/final_report_CAAS.pdf` (33 pages, clean compile).
Remaining: AWS deployment, slides, video demo, and optional near-hourly real-time upgrade.

---

## Session 2 Completed (2026-04-09)

### Final Report — all 8 sections written and compiled
- `01_introduction.tex` — problem, objectives, contributions with real metrics
- `02_data_engineering.tex` — 3 sources, 45-feature table, S3 layout, orchestration
- `03_ml_development.tex` — corrected metrics from JSON, XGBoost/LSTM/ablation/Scenario C/SHAP
- `04_mlops.tex` — architecture, API endpoints, CI/CD workflows, drift policy, Terraform
- `05_performance_analysis.tex` — full comparison table, latency, scalability, cost (~$0.55/day)
- `06_conclusion.tex` — 5 findings, 4 limitations, 5 future work items
- `07_references.tex` — 18 proper citations (PCD, ERA5, FIRMS, XGBoost, SHAP, LSTM, WHO, etc.)
- `08_appendix.tex` — 11-step reproduction guide + full metric tables + SHAP top-5 per horizon
- Abstract written with actual numbers (MAE 5.31/6.91/8.34, R²=0.824/0.736/0.612)

### Near-Hourly Real-Time Upgrade — PLANNED, NOT STARTED
**Task #15** — kick off when ready. Summary:
- Change cron from `0 23 * * *` (once/day) to `0 */3 * * *` (every 3 hours)
- Switch `fetch_pm25_live.py` to air4thai hourly endpoint
- Switch `fetch_weather.py` to Open-Meteo **forecast** API (free, at `api.open-meteo.com/v1/forecast`) instead of ERA5 reanalysis — this also fixes the "historical weather only" limitation for t+3/t+7
- Update `build_features.py` to handle sub-daily timestamps
- Update `run_inference.py` and FastAPI `/forecast` to include inference timestamp
- Key files: `daily_pipeline.yml`, `fetch_pm25_live.py`, `fetch_weather.py`, `build_features.py`, `run_inference.py`, `serve/app.py`

---

## Folder Structure

```
Proposal Presentation/
├── 01_Proposal/              ← LaTeX source + compiled PDF + all figures
│   ├── progress_report_CAAS.tex   ← MAIN SOURCE FILE (62 pages)
│   ├── progress_report_CAAS.pdf   ← COMPILED OUTPUT (latest)
│   ├── fig_cloud_architecture.png
│   ├── fig_model_promotion.png
│   ├── fig_daily_pipeline.png
│   ├── fig_sequence_flow.png
│   ├── fig_mlflow_runs.png
│   ├── fig_streamlit_dashboard.png
│   ├── fig_drift_output.png
│   ├── fig_actual_vs_predicted.png
│   ├── fig_feature_importance.png
│   ├── fig_confusion_matrix.png
│   ├── fig_haze_breakdown.png
│   └── fig_firms_ablation.png
├── 02_Presentation/          ← Empty — PPTX not started yet
├── 03_Data/
│   ├── raw/                  ← Raw PM2.5 (PCD Excel), weather, FIRMS CSVs
│   ├── processed/
│   │   └── features.csv      ← ML-ready 45-feature dataset (5,478 rows)
│   └── results/
│       ├── drift_summary.json
│       ├── drift_report_20260403.html
│       ├── xgboost_t1/t3/t7_test_predictions.csv
│       ├── lstm_t1/t3/t7_test_predictions.csv
│       ├── ablation_summary.json
│       └── ablation_no_firms_t1/t3/t7_test_predictions.csv
├── 04_Scripts/
│   ├── parse_pm25.py         ← PCD Excel → cleaned CSV
│   ├── fetch_weather.py      ← Open-Meteo API fetch
│   ├── fetch_firms.py        ← NASA FIRMS API fetch
│   ├── run_firms_batched.py  ← Batch FIRMS historical fetch
│   ├── build_features.py     ← Feature engineering (45 features)
│   ├── train_xgboost.py      ← XGBoost training (t+1/3/7) + MLflow logging
│   ├── train_lstm.py         ← LSTM training (t+1/3/7) + MLflow logging
│   ├── train_xgboost_no_firms.py ← Scenario D ablation (39 features)
│   ├── generate_eval_plots.py    ← confusion matrix + haze breakdown plots
│   ├── generate_ablation_plot.py ← FIRMS ablation bar chart
│   ├── serve/
│   │   ├── app.py            ← FastAPI inference server
│   │   └── dashboard.py      ← Streamlit dashboard
│   └── monitoring/
│       └── evidently_report.py   ← PSI + KS drift monitor (updated policy 2026-04-03)
├── 05_Reference/
│   ├── Project Guideline_st126055_st125975.pdf
│   ├── MLOPS2026 grading rubrics - Proposal rubrics.pdf
│   ├── Project Description.pdf
│   ├── final_ref.md          ← Final report rubric + requirements
│   └── monitoring_drift_policy_update_2026-04-03.md
└── 06_Handoff/
    └── CAAS_STATUS.md        ← THIS FILE
```

---

## Model Results (Key Numbers)

### XGBoost (Champion Model)
| Horizon | MAE | RMSE | R² | AUROC |
|---------|-----|------|----|-------|
| t+1 | 6.11 | 10.23 | 0.81 | 0.97 |
| t+3 | 7.37 | 12.45 | 0.74 | 0.96 |
| t+7 | 8.44 | 13.87 | 0.69 | 0.96 |

### LSTM (Comparison)
| Horizon | MAE | RMSE | R² |
|---------|-----|------|----|
| t+1 | 6.68 | 11.10 | 0.77 |
| t+3 | 9.27 | 14.82 | 0.65 |
| t+7 | 8.75 | 14.20 | 0.68 |

**XGBoost wins on all horizons.** Especially t+3 where it's 26% better MAE.

### Persistence Baseline (floor to beat)
| Horizon | MAE |
|---------|-----|
| t+1 | 5.30 |
| t+3 | 8.97 |
| t+7 | 10.93 |

### Scenario D — FIRMS Ablation
Removing 6 fire hotspot features → MAE worse by 4.3–6.8% across all horizons. Fire data confirmed valuable.

---

## MLflow Experiments
- **CAAS-XGBoost** — 3 runs (XGBoost-t1, t3, t7) ✅
- **CAAS-LSTM** — 3 runs (LSTM-t1, t3, t7) ✅
- **CAAS-Ablation-NoFIRMS** — 3 runs ✅
- MLflow UI: `mlflow ui` from `Proposal Presentation/` dir → `localhost:5000`

---

## How to Run Each Component

### 1. Feature Engineering
```bash
cd "Proposal Presentation/04_Scripts"
source ../caas-env/bin/activate
python build_features.py
```

### 2. Train XGBoost
```bash
python train_xgboost.py
```

### 3. Train LSTM
```bash
python train_lstm.py
# Uses Apple M4 Pro GPU via tensorflow-metal
# Takes ~2 min per horizon
```

### 4. Run FastAPI Server
```bash
cd serve/
uvicorn app:app --reload --port 8000
# Endpoints: /health /forecast /predict /history /model/info
```

### 5. Run Streamlit Dashboard
```bash
cd serve/
streamlit run dashboard.py
# → localhost:8501
# Note: FastAPI must be running first for live data; falls back to demo data if not
```

### 6. Run Drift Monitor
```bash
cd monitoring/
python evidently_report.py
# Optional flags: --strict-exit  --trigger-retrain
# Output: drift_summary.json + drift_report_YYYYMMDD.html
```

### 7. Compile LaTeX Report
```bash
cd "Proposal Presentation/01_Proposal"
pdflatex progress_report_CAAS.tex && pdflatex progress_report_CAAS.tex
open progress_report_CAAS.pdf
```

### 8. MLflow UI
```bash
cd "Proposal Presentation/"
mlflow ui
# → localhost:5000
```

---

## Progress Report Status: ✅ COMPLETE

All 12 figures embedded, all tables fixed, timeline updated.

| Chapter | Content | Status |
|---------|---------|--------|
| Ch1 Introduction | Problem statement, objectives | ✅ |
| Ch2 Background | PM2.5, ML literature, MLOps | ✅ |
| Ch3 Methodology | Data pipeline, features, models | ✅ |
| Ch4 Architecture | AWS diagram, CI/CD, monitoring | ✅ |
| Ch5 Experimental Plan | Dataset, baselines, metrics, timeline | ✅ |
| Ch6 Implementation Progress | Scripts, data status, screenshots | ✅ |
| Ch7 Preliminary Results | XGBoost + LSTM results, 8 figures | ✅ |
| Ch8 Experimental Scenarios | A/B/C/D with tables + ablation figure | ✅ |

---

## 360° Audit Findings (2026-04-09)

Full project audit done. Beyond the metric discrepancies (below), discovered:

### Critical gap: CI/CD workflows reference scripts that don't exist
`.github/workflows/daily_pipeline.yml` and `retrain.yml` already exist but reference 5 missing scripts:
- `fetch_pm25_live.py` — daily PM2.5 fetch from air4thai
- `run_inference.py` — generate forecasts from loaded models
- `upload_to_s3.py` — push results to S3
- `validate_candidate.py` — champion/challenger gate (≥5% MAE improvement + F1≥0.75)
- `promote_model.py` — MLflow Staging→Production transition

**If professor inspects .github/workflows/, broken CI is worse than no CI.** Must write these scripts before showing workflows to anyone.

### Other missing pieces
- ❌ AWS infrastructure (S3/EC2/IAM all zero)
- ❌ Dockerfile
- ❌ Terraform (rubric requires IaC)
- ❌ Zero tests (no pytest)
- ❌ No SHAP analysis
- ❌ No Scenario C precision-recall threshold analysis
- ❌ Final report LaTeX (now scaffolded in `07_Final/report/`)
- ❌ PPTX slides (now outlined in `07_Final/slides/SLIDES_OUTLINE.md`)
- ❌ Video recording

### Folder created: `07_Final/`
```
07_Final/
├── README.md
├── report/
│   ├── final_report_CAAS.tex
│   ├── sections/ (8 modular .tex files)
│   └── figures/
├── slides/
│   ├── SLIDES_OUTLINE.md
│   ├── assets/
│   └── exports/
└── video/
```

---

## Metric Discrepancy Audit (2026-04-07)

Audited all training scripts and result JSONs. Training code is legitimate (not rushed). Found that **RMSE and R² numbers in the progress report do not match actual results** — MAE values are correct but RMSE/R² appear to be from an older run or wrong split.

### Actual vs Reported Numbers

**XGBoost (actual from xgboost_summary.json):**
| Horizon | MAE | RMSE (actual) | RMSE (report) | R² (actual) | R² (report) |
|---------|-----|---------------|---------------|-------------|-------------|
| t+1 | 6.11 ✓ | 10.62 | 10.23 | 0.779 | 0.81 |
| t+3 | 7.37 ✓ | 12.30 | 12.45 | 0.704 | 0.74 |
| t+7 | 8.44 ✓ | **14.45** | **13.87** | **0.594** | **0.69** |

**LSTM (actual from lstm_summary.json):**
| Horizon | MAE | RMSE (actual) | RMSE (report) | R² (actual) | R² (report) |
|---------|-----|---------------|---------------|-------------|-------------|
| t+1 | 6.68 ✓ | 11.68 | 11.10 | 0.743 | 0.77 |
| t+3 | 9.27 ✓ | **16.28** | **14.82** | **0.503** | **0.65** |
| t+7 | 8.75 ✓ | **15.60** | **14.20** | **0.546** | **0.68** |

**Decision needed:** retrain (try to improve numbers, especially LSTM t3/t7) OR just correct the numbers in the final report.
Options discussed — see suggestions section below.

---

## What's Next (Final Report)

Waiting for professor feedback on progress report first.

### Final Rubric Breakdown
| Criteria | Weight | Current Est. | Gap |
|----------|--------|-------------|-----|
| Problem Selection | 10% | ~9/10 | Minimal |
| **Data Engineering** | **25%** | ~18/25 | AWS S3/Lambda not deployed |
| ML Model Development | 15% | ~13/15 | Missing SHAP + Scenario C threshold |
| **MLOps Implementation** | **20%** | ~10/20 | No AWS deploy, no CI/CD live |
| Project Report | 10% | ~7/10 | Missing Conclusion + Appendix |
| Impact | 5% | ~4/5 | Good |
| **Presentation + Demo** | **15%** | 0/15 | Not started |

### Priority Task List (Final)
0. 🔴 Decide: retrain LSTM (improve t3/t7 numbers) OR correct report numbers to match actual JSON results
1. 🔴 AWS deployment (S3 + EC2) — biggest point gap
2. 🔴 GitHub Actions YAML files + 1 live run
3. 🔴 PPTX presentation (10 min + demo)
4. 🟡 Scenario C: precision-recall + optimal threshold
5. 🟡 SHAP analysis
6. 🔴 Final report: add Conclusion + Performance Analysis + Appendix
7. 🔴 Video recording (required deliverable per final_ref.md)

### Final Report Additional Sections Needed
- **Performance Analysis** section with cost calculation ($/hr or $/day)
- **Conclusion** chapter (summary + future work)
- **Appendix** — step-by-step system reproduction guide
- Update Ch6 to reflect all completed implementation

---

## Known Issues / Gotchas

| Issue | Notes |
|-------|-------|
| pip resolver breaks on evidently | Use `uv pip install -r requirements.txt` instead |
| LSTM NaN training | Fixed: add `fillna(0)` fallback after median imputation in `train_lstm.py` |
| evidently HTML report fails | `hotspot_50km` sparse → HTML skipped but `drift_summary.json` saves fine |
| Streamlit "cannot connect" | FastAPI must be running first on port 8000 |
| LaTeX compile needs 2 passes | Always run `pdflatex` twice for correct TOC + references |
| caas-env activation | `source "Proposal Presentation/caas-env/bin/activate"` from project root |

---

## Environment

- **Python env:** `caas-env/` (virtualenv inside Proposal Presentation/)
- **Key packages:** xgboost, tensorflow-metal, mlflow, evidently, fastapi, streamlit, evidently
- **MLflow tracking URI:** local `mlruns/` folder
- **Hardware:** Apple M4 Pro (GPU via tensorflow-metal for LSTM)

---

## Drift Monitoring Policy (Updated 2026-04-03)

Retrain triggered if:
- `mae_flag = True` (7-day rolling MAE > 15 µg/m³), OR
- `core_drift_count >= 2` (pm25_lag1 + pm25_roll7_mean both drift), OR
- `core_drift_count >= 1` AND `soft_drift_count >= 2`

Seasonal KS reference used for: `wind_speed`, `hotspot_50km`, `is_haze_season`
Zero-inflation PSI suppressed for sparse features.

Latest drift run (2026-04-03): **DRIFT DETECTED** — Dec 2025 vs training baseline.
Core drift: pm25_lag1 (PSI=10.52), pm25_roll7_mean (PSI=12.36). MAE still OK (1.75 µg/m³).
This is **expected** seasonal behavior, not a model failure.
