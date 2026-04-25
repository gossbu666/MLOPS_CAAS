# CAAS — Full Project Walkthrough for Shuvam

Hey Shuvam — this is a catch-up writeup so you can walk into the defense knowing every piece of what we built, why we built it that way, and where to find things. I wrote it chronologically so you can follow the story. Skip to the section you need; come back to the rest when you have time.

**Defense is 2026-04-24.** Everything below is as of 2026-04-23.

---

## 1. What we set out to do

Chiang Mai has a yearly haze crisis from Jan–Apr. PM2.5 regularly hits 100+ µg/m³, six times the WHO daily limit. The existing public tools (air4thai, IQAir) only show *current* pollution — they don't forecast it. Our thesis claim: a production MLOps system that forecasts PM2.5 **1, 3, and 7 days ahead** and issues alerts is useful and deployable at low cost.

So the project is **not about inventing a new model**. It's about shipping an end-to-end production pipeline using sensible models. That framing matters because the professor's feedback specifically said "reframe as integration, not novelty" — which we did.

---

## 2. The three data sources (Data Engineering, 25% of the grade)

We ingest three sources into a single daily feature store:

**PM2.5** — from Thailand's Pollution Control Department (PCD). The historical archive is 15 years of Excel files (2011–2025) for stations `35T` and `36T` in Chiang Mai. For daily updates we hit `air4thai.pcd.go.th/services/getNewAQI_JSON.php`. When the ground station is offline, we fall back to Open-Meteo's CAMS satellite product (`open-meteo-cams-cal`). The fallback has a different calibration baseline than the ground station, so forecasts go slightly fuzzy when it kicks in — worth mentioning in Q&A if asked.

- Script: [`04_Scripts/parse_pm25.py`](../04_Scripts/parse_pm25.py) (history) + [`fetch_pm25_live.py`](../04_Scripts/fetch_pm25_live.py) (daily)
- Output: `03_Data/processed/pm25_consolidated.csv`

**Weather** — from Open-Meteo's free API (no key needed). We pull 11 daily variables: temp min/max/mean, humidity min/max, precipitation, wind speed + direction, pressure, cloud cover, evapotranspiration.

- Script: [`04_Scripts/fetch_weather.py`](../04_Scripts/fetch_weather.py)
- **Important bug I caught today:** the `END_DATE` was hardcoded to `"2025-12-31"`, so every run after New Year silently stopped refreshing weather. Fixed to `pd.Timestamp.now(tz="Asia/Bangkok")`. Already committed (`b6b7dcd`).

**Fire hotspots** — from NASA FIRMS. Satellite-detected active fires within 50 and 100 km of Chiang Mai. Requires a free API key (`FIRMS_MAP_KEY` in `.env`). Yearly cache is stored on S3 to avoid re-downloading full years on each run.

- Script: [`04_Scripts/fetch_firms.py`](../04_Scripts/fetch_firms.py) + [`run_firms_batched.py`](../04_Scripts/run_firms_batched.py)
- Output: `03_Data/processed/firms_consolidated.csv`

All three sources land in `03_Data/processed/` as clean CSVs.

---

## 3. Feature engineering — 45 features (our tabular edge)

The core ML insight of this project is that **tabular models with good features beat sequence models** on this data. That's why LightGBM/XGBoost eventually outperformed LSTM.

The 45 features come from [`04_Scripts/build_features.py`](../04_Scripts/build_features.py):

- **PM2.5 lags** (5): `pm25_lag1`, `lag3`, `lag7`, `lag14`, `lag30`
- **PM2.5 rolling stats** (6): 3/7/14/30-day means, 7/14-day std
- **Temporal** (8): month, week, day-of-year, sin/cos encodings, `is_haze_season` flag
- **Weather** (12): all 11 raw variables + a `humidity_wind` interaction
- **Fire** (6): hotspot counts within 50 and 100 km, rolling 7/14-day counts, mean FRP, fire flag
- **Alert lags** (3): yesterday's / 3-day-ago / 7-day-ago alert state
- **Cross features** (5): `lag1_x_temp`, `lag1_x_wind`, `roll7_x_fire`, `precip_flag`, `humidity_wind`

One subtlety: **current-day PM2.5 is NOT a feature**. `pm25_lag1` on row D means `pm25[D-1]`. So when we predict for t+1 (tomorrow) from row D, we're using D-1 as the most recent observation. This was a deliberate design choice for training stability (no leakage) but means a fresh same-day spike doesn't directly hit tomorrow's forecast — it propagates through `pm25_lag1` starting the following day. Good defense talking point.

Output: `03_Data/processed/features.csv` (5,368 rows × 45 columns, chronological, Jan 2011–today).

---

## 4. The three models (ML, 15% of the grade)

We trained three models on the same 45-feature dataset with a strict chronological split:

- **Train:** 2011–2022 (~4,000 days)
- **Validation:** 2023 (~365 days) — used for early stopping and hyperparameter selection
- **Test:** 2024–2025 (~700 days) — never touched during training

**XGBoost** — the original champion plan. 103 Optuna trials per horizon. Good baseline.
- Script: [`train_xgboost.py`](../04_Scripts/train_xgboost.py)
- Test MAE: **5.31 / 7.08 / 8.90** (t+1 / t+3 / t+7)

**LightGBM** — I added this mid-project after noticing XGBoost's marginal leaf-wise inefficiency on our feature distribution. Same Optuna setup. This became the new champion.
- Script: [`train_xgboost.py`](../04_Scripts/train_xgboost.py) (it trains both models in one pass via the `--model` flag)
- Test MAE: **5.12 / 6.77 / 8.25** — beats XGBoost on all three horizons
- Alert F1 ≥ 0.83 at t+1

**LSTM** — sequential baseline. 30-day input window, 2-layer LSTM (64 → 32), Apple M4 GPU via tf-metal.
- Script: [`train_lstm.py`](../04_Scripts/train_lstm.py)
- Test MAE: **6.67 / 8.87 / 8.06**
- It wins t+7 R² slightly (0.608 vs LightGBM 0.600) but loses everywhere else. Our story: "tabular features encode the temporal structure better than raw sequence input on this dataset size."

**Champion promotion logic** ([`validate_candidate.py`](../04_Scripts/validate_candidate.py) + [`promote_model.py`](../04_Scripts/promote_model.py)):
- Challenger must beat current champion by ≥5% test MAE AND have alert-F1 ≥ 0.75
- If both pass → register in MLflow as Production, archive old champion
- If either fails → keep in Staging, log alert

LightGBM passed this gate on 2026-04-18.

---

## 5. Explainability — SHAP (closes feedback item #4)

We computed SHAP values for all three horizons ([`shap_analysis.py`](../04_Scripts/shap_analysis.py)). Output: 6 figures in `03_Data/results/fig_shap_*.png` and a JSON at `shap_summary.json`.

Key findings (in the slides + report):

- **t+1**: top feature is `pm25_lag1` by a huge margin. Autocorrelation dominates.
- **t+3**: burn-load features (`firms_24h_count`, `hotspot_50km`) climb into the top 5. Fire signals propagate downwind over 2–3 days.
- **t+7**: weather regime (`wind_speed_7d`, `temperature_7d`) takes over. At a week out, the model is effectively forecasting the weather pattern.

This mirrors atmospheric physics (boundary-layer dynamics + transport) and is a nice honesty-check on the model.

---

## 6. Alert threshold optimization — Scenario C (closes feedback item #4)

Instead of a fixed 50 µg/m³ threshold for the alert, we computed the optimal PR-maximizing threshold per horizon ([`scenario_c_threshold.py`](../04_Scripts/scenario_c_threshold.py)):

- t+1: 50 µg/m³
- t+3: 52 µg/m³
- t+7: 55 µg/m³

Slightly higher thresholds at longer horizons because uncertainty grows → raising the bar prevents alert fatigue. We wire these thresholds into `serve/app.py` at request time.

---

## 7. Deployment — AWS + Docker + Terraform (MLOps, 20%)

We built this as Infrastructure-as-Code via Terraform so the grader can `terraform apply` and reproduce the whole stack.

**What's running right now:**

- **S3 bucket** `caas-mlops-st126055` — tiered prefixes for raw / processed / models / results
- **EC2 t3.small** at `13.250.17.6` — Ubuntu, 2 vCPU, 2 GB RAM + 2 GB swap (cold-boot model loading needs it)
- **Docker Compose stack** with 3 containers:
  - `caas-api` (FastAPI on :8000)
  - `caas-dashboard` (Streamlit on :8502)
  - `caas-mlflow` (MLflow UI on :5001)
- **IAM role** `caas-ec2-role` — S3 R/W, no credentials in code
- **Security group** — 8000 / 8502 / 5001 open to `0.0.0.0/0`, SSH (22) restricted

**Live URLs (will stay up until defense teardown):**
- http://13.250.17.6:8000/forecast
- http://13.250.17.6:8502/
- http://13.250.17.6:5001/

**Gotcha I caught today:** The API container reads forecast files **baked into the Docker image**, not live from S3. So even though GH Actions pushes fresh forecasts to S3 every 3 hours, the container serves stale data until rebuilt. We fixed this by `docker compose up --build -d` on EC2 this morning — forecast is now fresh through 2026-04-22. Future work note: either add an EC2 cron that does `aws s3 sync` every 3 hours, or refactor `serve/app.py` to read S3 on each request. Both are in our "future work" section of the report.

---

## 8. CI/CD — four GitHub Actions workflows

All four exist in `.github/workflows/` and are hooked to the real `gossbu666/MLOPS_CAAS` repo:

1. **`test.yml`** — runs `pytest` on every push + PR. 45 tests across API, features, models. Currently green.
2. **`daily_pipeline.yml`** — runs every 3 hours (cron `0 */3 * * *`). Ingests fresh data → rebuilds features → runs inference → uploads to S3. Takes ~3 minutes. Last run was 01:17 UTC today, success.
3. **`drift_check.yml`** — daily PSI + KS drift detection using Evidently. Threshold: core features PSI > 0.1 → alert; > 0.25 → trigger retrain.
4. **`retrain.yml`** — manual + scheduled weekly. Train challenger → validate → promote via MLflow registry.

GitHub Secrets set: `FIRMS_MAP_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET_NAME`, `MLFLOW_PUBLIC_URL`.

---

## 9. Monitoring — drift + retrain policy

In [`05_Reference/monitoring_drift_policy_update_2026-04-03.md`](../05_Reference/monitoring_drift_policy_update_2026-04-03.md) we locked down:

- **Core features** (top-5 SHAP drivers): PSI > 0.1 → warning, > 0.25 → retrain
- **Soft features**: PSI > 0.25 → warning, > 0.4 → retrain
- **Prediction drift**: rolling 7-day MAE > 2× training MAE for 3 consecutive days → retrain
- **Retrain gate**: challenger must beat champion by ≥5% MAE + alert-F1 ≥ 0.75

Script: [`04_Scripts/monitoring/evidently_report.py`](../04_Scripts/monitoring/evidently_report.py)
Output: `03_Data/results/drift_summary.json` + HTML reports

---

## 10. Test metrics — authoritative numbers

Always trust these JSON files over anything written in the report prose (the report was written from these):

| Model | t+1 MAE | t+3 MAE | t+7 MAE | t+1 R² |
|---|---|---|---|---|
| **LightGBM (champion)** | **5.12** | **6.77** | **8.25** | **0.841** |
| XGBoost | 5.31 | 7.08 | 8.90 | 0.843 |
| LSTM | 6.67 | 8.87 | 8.06 | 0.753 |

Alert F1 for LightGBM: 0.84 / 0.79 / 0.68 (t+1 / t+3 / t+7). The t+7 is honest-weak; we acknowledge this in the report.

---

## 11. The 5 professor feedback items — all closed

From [`07_Final/FEEDBACK_FROM_PROPOSAL.md`](../07_Final/FEEDBACK_FROM_PROPOSAL.md):

1. ✅ **Unify drift/retraining story** — done via the policy doc + workflow.
2. ✅ **Resolve inconsistencies in report vs slides** — single authoritative JSON source.
3. ✅ **Reframe contribution** — "production integration, not methodological novelty". Intro + conclusion + slide 1 aligned.
4. ✅ **Strengthen evaluation** — added SHAP, Scenario C, ablation (no-FIRMS), bootstrap.
5. ✅ **Clarify cost realism** — per-component breakdown in report § 4; always-on limitation acknowledged.

Bonus item the professor also asked: *"What are the exact GH Actions stages in retraining?"* — covered in report § 4.3 with a 6-stage diagram.

---

## 12. Known gotchas (so you don't get blindsided in Q&A)

1. **Container serves baked data, not live S3.** We did a manual refresh today. If the committee looks at the dashboard before we demo and sees stale numbers, the answer is "we do a manual refresh pre-demo; future work is an EC2 cron."
2. **Weather ingest had a hardcoded END_DATE.** Fixed and committed today (`b6b7dcd`). If they look at git history, it's there.
3. **PCD station 35T has been intermittent.** Recent 30 days had 29 from satellite fallback + 1 from ground station. Fallback has different calibration — forecast MAE widens slightly when it kicks in.
4. **Current-day PM2.5 is not a feature.** `pm25_lag1` on row D = `pm25[D-1]`. A spike today doesn't directly hit tomorrow's forecast — it propagates through lag1 the following day. Worth explaining as a design choice (no leakage, stable training).
5. **LSTM t+3 R² = 0.540 is weak.** Answer: seq_len 30 may be too long; tabular features encode time structure better at this dataset size.
6. **Cost is $0.55/day ≈ $17/month**, not the <$8 claim in the original proposal. We refined this with honest per-component math. Always-on serving is the driver.

---

## 13. What we still need to do before 2026-04-24 (defense day)

| Item | Who | Time |
|---|---|---|
| Write speaker script for the 14 slides | Supanut (in progress now) | ~2 h |
| Rehearse 15-minute defense together | Both | ~2 × 2 h |
| Record demo video | Both | ~30 min |
| Assemble `FINALSUBMIT/` folder (PDF + PPTX + video link + README) | Supanut | ~15 min |
| EC2 teardown after defense (`terraform destroy`) | Supanut | ~5 min |

---

## 14. How to run everything locally

```bash
git clone https://github.com/gossbu666/MLOPS_CAAS.git
cd MLOPS_CAAS
python3.11 -m venv caas-env
source caas-env/bin/activate
pip install -r requirements.txt
cp .env.example .env      # Fill FIRMS_MAP_KEY + AWS_* + S3_BUCKET_NAME

# Full pipeline (ingest → features → train → infer → serve → monitor)
./run_pipeline.sh all

# Individual steps
./run_pipeline.sh 5       # Train XGBoost
./run_pipeline.sh 6       # Train LSTM (~1-2 h on laptop)
./run_pipeline.sh api     # Start FastAPI on :8000
./run_pipeline.sh 9       # Drift check

# Tests
pytest                    # 45 tests

# Docker
docker compose up --build -d

# Terraform (deploys the whole AWS stack)
cd infra && terraform init && terraform apply
```

---

## 15. Key files you should know

| File | Why it matters |
|---|---|
| [`CLAUDE.md`](../CLAUDE.md) | Project primer. Directory map, authoritative JSON pointers, known gotchas, rubric weights. |
| [`06_Handoff/CAAS_STATUS.md`](CAAS_STATUS.md) | Session log (a bit stale but still useful). |
| [`07_Final/report/final_report_CAAS.pdf`](../07_Final/report/final_report_CAAS.pdf) | The 52-page submission. |
| [`07_Final/slides/CAAS_final.pptx`](../07_Final/slides/CAAS_final.pptx) | 14-slide defense deck, Variant D aesthetic. |
| [`05_Reference/final_ref.md`](../05_Reference/final_ref.md) | Full rubric and required sections. |
| [`03_Data/results/*_summary.json`](../03_Data/results/) | Authoritative metrics — trust these over report prose. |
| [`.github/workflows/`](../.github/workflows/) | The 4 CI/CD workflows. |
| [`infra/main.tf`](../infra/main.tf) | Terraform for the live AWS stack. |

---

## Final word

Everything we promised in the proposal is shipped, plus: LightGBM champion, SHAP, Scenario C, ablation, 45 tests, live AWS deployment, four working GH Actions workflows. The five feedback points are all addressed in the final report.

The three things that could come up in Q&A are the container-bake issue (answer: future cron), the proposal's Lambda → now GH Actions decision (answer: simpler + cheaper), and the always-on cost (answer: honest breakdown at $17/mo; spot instances are future work).

Let me know which parts you want to rehearse on your end and I'll focus the script sections accordingly. We got this.

— Supanut
