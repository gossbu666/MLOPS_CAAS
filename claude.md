# CAAS — ChiangMai Air Quality Alert System

> Context primer for Claude Code sessions working on this capstone project. Read this first.

---

## 1. Project summary

**CAAS** is an end-to-end MLOps system that forecasts PM2.5 air quality in Chiang Mai at **t+1 / t+3 / t+7 day horizons** and issues hazard alerts. Built for the **AT82.9002 Data Engineering and MLOps** capstone at AIT (2026 cohort).

- **Students:** Supanut Kompayak (st126055) · Shuvam Shrestha (st125975)
- **Champion model:** XGBoost (45 features). **Comparison model:** LSTM (Keras).
- **Data sources:** Thai PCD PM2.5 Excel archives, Open-Meteo weather, NASA FIRMS fire hotspots.
- **Rubric weights:** DE 25%, MLOps 20%, Presentation+Demo 15%, ML 15%, Report 10%, Problem 10%, Impact 5%.

> ⚠️ Working directory contains a **space** in the path (`Proposal Presentation/`). Quote all shell paths. `run_pipeline.sh` is hardcoded to this layout.

---

## 2. Directory map

```
Proposal Presentation/
├── 01_Proposal/          ← Progress-report LaTeX + PDF (62 pages) + 12 figures
├── 02_Presentation/      ← EMPTY (legacy; superseded by 07_Final/slides)
├── 03_Data/
│   ├── raw/              ← PCD PM2.5 Excel, FIRMS yearly cache, FIRMS batch outputs
│   ├── processed/        ← features.csv (45 feats), pm25/weather/firms_consolidated.csv
│   ├── models/           ← xgboost_t{1,3,7}.json  +  lstm_t{1,3,7}.keras + *_scaler.pkl
│   └── results/          ← AUTHORITATIVE metrics JSONs + prediction CSVs + SHAP/PR figs
├── 04_Scripts/
│   ├── parse_pm25.py / fetch_weather.py / fetch_firms.py / run_firms_batched.py
│   ├── build_features.py
│   ├── train_xgboost.py / train_xgboost_no_firms.py / train_lstm.py
│   ├── fetch_pm25_live.py / run_inference.py          ← daily pipeline
│   ├── upload_to_s3.py / validate_candidate.py / promote_model.py  ← champion/challenger
│   ├── shap_analysis.py / scenario_c_threshold.py     ← explainability + PR thresholds
│   ├── generate_eval_plots.py / generate_ablation_plot.py
│   ├── monitoring/evidently_report.py                 ← PSI + KS drift
│   └── serve/app.py (FastAPI) + dashboard.py (Streamlit)
├── 05_Reference/         ← Rubric, guideline, drift policy update (AUTHORITY)
├── 06_Handoff/           ← CAAS_STATUS.md (living log; update after each session)
├── 07_Final/             ← Final deliverables (active submission folder)
│   ├── report/           ← final_report_CAAS.tex + sections/ + figures/ + PDF
│   ├── slides/           ← SLIDES_OUTLINE.md (PPTX NOT YET BUILT)
│   ├── video/            ← EMPTY (demo video NOT YET RECORDED)
│   ├── README.md
│   └── FEEDBACK_FROM_PROPOSAL.md  ← Professor feedback to address in final report
├── FINALSUBMIT/          ← ⚠️ Contains PROPOSAL-phase PDFs, not final deliverables
├── infra/                ← Terraform: S3 + IAM + SG + EC2 t3.micro (NOT YET APPLIED)
├── tests/                ← pytest: conftest.py + test_api.py + test_features.py + test_models.py
├── .github/workflows/    ← test.yml, daily_pipeline.yml, drift_check.yml, retrain.yml
├── mlruns/               ← MLflow local tracking backend
├── caas-env/             ← Python 3.11 virtualenv (2.5 GB; includes tf-metal for Apple M4)
├── Dockerfile            ← Multi-stage FastAPI image (non-root user, healthcheck)
├── run_pipeline.sh       ← Local orchestrator (Steps 0–10)
├── pytest.ini            ← testpaths=tests, filterwarnings suppress tf noise
├── requirements.txt      ← Full pipeline deps (tf, xgboost, mlflow, evidently, ...)
├── requirements-serve.txt← Slim deps for Docker inference image
├── .env                  ← ⚠️ EXISTS AT ROOT — verify .gitignore excludes it
├── .env.example          ← Template (FIRMS_MAP_KEY, AWS_*, S3_BUCKET_NAME, EC2_HOST, ...)
├── progress_report_CAAS.pdf  ← Old progress-report compile (also in 01_Proposal/)
└── CLAUDE.md             ← THIS FILE
```

---

## 3. Key files to know

### Authoritative metric sources (always trust over report tables)
- `03_Data/results/xgboost_summary.json` — val + test + alert metrics for t+1/3/7
- `03_Data/results/lstm_summary.json`
- `03_Data/results/ablation_summary.json` — Scenario D (no-FIRMS) comparison
- `03_Data/results/scenario_c_summary.json` — optimal PR thresholds per horizon
- `03_Data/results/shap_summary.json` — feature attributions per horizon
- `03_Data/results/drift_summary.json` — latest PSI/KS drift run

**Current numbers (from JSON, 2026-04-09 run):**

| | XGBoost t+1 | t+3 | t+7 | LSTM t+1 | t+3 | t+7 |
|--|--|--|--|--|--|--|
| test MAE | 5.31 | 6.91 | 8.34 | 6.67 | 8.87 | 8.06 |
| test R² | 0.824 | 0.736 | 0.612 | 0.753 | 0.540 | 0.608 |
| alert F1 | 0.839 | 0.787 | 0.684 | 0.753 | 0.593 | 0.694 |

### Rubric / requirements (READ BEFORE ANY AUDIT)
- `05_Reference/final_ref.md` — full rubric with 7 required report sections
- `05_Reference/Project Guideline_st126055_st125975.pdf`
- `05_Reference/monitoring_drift_policy_update_2026-04-03.md` — current drift/retrain policy
- `07_Final/FEEDBACK_FROM_PROPOSAL.md` — professor feedback the final report must address

### Living status
- `06_Handoff/CAAS_STATUS.md` — session log; update after every meaningful change

### Final deliverables
- `07_Final/report/final_report_CAAS.pdf` — 33-page compiled final report
- `07_Final/slides/SLIDES_OUTLINE.md` — 14-slide plan (PPTX not built)
- `07_Final/video/` — empty

---

## 4. Tech stack (pinned versions)

| Layer | Tool | Version |
|--|--|--|
| Language | Python | 3.11 |
| ML | xgboost / scikit-learn | 2.1.1 / 1.5.1 |
| DL | tensorflow (tf-metal on M4) | 2.17.0 |
| Tracking | MLflow | 2.15.1 (local `mlruns/` backend) |
| Serving | FastAPI + uvicorn | 0.112 / 0.30.6 |
| UI | Streamlit + altair | 1.37.1 / >=5 |
| Drift | Evidently + scipy | 0.4.33 / >=1.11 |
| Data APIs | openmeteo-requests, requests-cache, retry-requests | — |
| Cloud | boto3 | 1.35.0 |
| IaC | Terraform + AWS provider | >=1.5 / ~>5.0 |
| Tests | pytest + pytest-cov | 8.3.2 / 5.0.0 |
| CI/CD | GitHub Actions | `ubuntu-latest`, Python 3.11 |
| Container | Docker | multi-stage python:3.11-slim |

---

## 5. Review personas

When the user asks for a review or audit, pick the persona(s) that match the ask. Each lists concrete artifacts to inspect in **this** project.

### 🔍 AUDITOR — rubric compliance
- Verify `07_Final/report/final_report_CAAS.pdf` contains all 7 sections from `05_Reference/final_ref.md`: Intro, Data Eng, ML, MLOps, **Performance Analysis with cost/day**, Conclusion, References, Appendix.
- Cross-check every metric in the PDF against `03_Data/results/*.json` (MAE/RMSE/R² and alert precision/recall/F1/AUROC for t+1/3/7).
- Confirm the 5 points raised in `07_Final/FEEDBACK_FROM_PROPOSAL.md` are explicitly addressed in the final report (drift/retrain story, report↔slides consistency, contribution framing, evaluation rigor, cost realism, GitHub Actions stages).
- Check deliverables per rubric: PPTX (15%) and video (required). Currently both missing.
- Verify MLflow runs exist in `mlruns/` for CAAS-XGBoost, CAAS-LSTM, CAAS-Ablation-NoFIRMS experiments.
- Confirm CI/CD claims in the report match `.github/workflows/` reality (workflows exist but haven't been run against live AWS).

### 🧠 ML ENGINEER
- Read `04_Scripts/train_xgboost.py` and `train_lstm.py`; verify chronological splits (train 2011–2022 / val 2023 / test 2024–2025) and no feature leakage via lag/rolling features.
- Confirm model files on disk (`03_Data/models/xgboost_t{1,3,7}.json`, `lstm_t{1,3,7}.keras`) correspond to the metrics in the JSON summaries (retrain pinned to a seed?).
- LSTM t+3 test R² = 0.540 is weak — inspect architecture in `train_lstm.py` (seq_len, depth, scaler fit scope).
- Verify `04_Scripts/validate_candidate.py` gate matches the report's claim (≥5% MAE improvement + alert-F1 ≥ 0.75).
- Check `shap_analysis.py` outputs (`fig_shap_summary_t{1,3,7}.png`, `fig_shap_waterfall_t{1,3,7}.png`) are referenced in the final report.
- Confirm `scenario_c_threshold.py` optimal thresholds are actually used in the alert logic inside `serve/app.py`.

### 👀 CODE REVIEWER — 5-axis (correctness / readability / architecture / security / performance)
- `04_Scripts/serve/app.py` — endpoint coverage vs `tests/test_api.py` (18 test functions). Hardcoded paths? Global state?
- `tests/` — are the 45 tests meaningful or assertion-light stubs? Do fixtures in `conftest.py` hit real files or mock?
- Shared feature-build logic between training and inference — ensure `04_Scripts/build_features.py` is the single source so inference features match training.
- `04_Scripts/monitoring/evidently_report.py` — PSI + KS thresholds match `05_Reference/monitoring_drift_policy_update_2026-04-03.md`?
- `run_pipeline.sh` — step ordering, error handling (`set -e`), env activation consistency.
- Dockerfile lines 47–51 copy selected CSVs only; stale-data risk if `run_pipeline.sh` regenerates them after build.

### 🔒 SECURITY + REPRODUCIBILITY
- **`.env` at repo root (413 bytes)** — verify it's in `.gitignore` and contains no real secrets committed to history.
- `infra/main.tf` line 183: `allowed_ssh_cidr` — check `infra/variables.tf` default; anything other than your IP/32 is a red flag.
- IAM policy (`main.tf` ~line 116): `s3:DeleteObject` is granted to the EC2 role — consider least-privilege (list+get+put only).
- EC2 `user_data` clones `https://github.com/gossbu666/MLOPS_CAAS.git` — repo must exist + be public (or replace with authenticated clone) for Terraform apply to succeed.
- Security groups open API (8000), MLflow (5000), SSH (22) to `0.0.0.0/0` for API/MLflow — fine for demo, risky for prod.
- Reproducibility: `tensorflow==2.17.0` pinned but dev machine uses **tf-metal** on Apple M4 — grader on Linux/Windows needs plain `tensorflow` with matching version; note this in the appendix.
- `python_version: "3.11"` in workflows, Dockerfile, and venv — consistent ✓.
- `requirements.txt` has all deps exact-pinned ✓. `requirements-serve.txt` is a slim subset — confirm it covers everything `serve/app.py` imports.
- `run_pipeline.sh` assumes `FIRMS_MAP_KEY` in `.env` — graders without a FIRMS key cannot reproduce end-to-end; appendix should note the free-tier signup.

### 💼 BUSINESS ANALYST — impact + cost realism
- Target population: ~1.2M residents in Chiang Mai metro (verify the number in the report; impact section claims this).
- Cost claim in report (~$0.55/day): breakdown check — EC2 t3.micro (~$0.01/h × 24 ≈ $0.24), S3 storage (~$0.02/GB × ~1 GB), egress, GitHub Actions minutes. Does the math land?
- Always-on services (FastAPI, Streamlit, MLflow, Evidently) — professor flagged cost realism in `FEEDBACK_FROM_PROPOSAL.md`. Is there a cost-scaling plan (spot instances, Lambda, scheduled shutdown)?
- Novelty framing: feedback says "position as strong integration, not novel forecasting method" — verify intro/conclusion wording.
- Alert utility: t+1 F1=0.839 is operationally usable; t+7 F1=0.684 — is this honest about downstream alert noise?
- Competitive differentiation vs `air4thai.pcd.go.th` which already publishes daily PM2.5 — where does CAAS add value? (Answer: multi-horizon forecast + SHAP explainability + fire-feature ablation.)

---

## 6. Slash-command suggestions for this project

Commands worth creating in `.claude/commands/`:

| Command | Purpose |
|--|--|
| `/audit-rubric` | AUDITOR sweep: final report sections vs `final_ref.md` + PPTX/video presence + deliverable checklist |
| `/verify-metrics` | Parse `03_Data/results/*.json` and grep final report PDF text for mismatches in MAE/RMSE/R²/F1 per horizon |
| `/check-feedback-addressed` | Cross-check each bullet in `07_Final/FEEDBACK_FROM_PROPOSAL.md` against the final report |
| `/reproduce-pipeline` | Dry-run `run_pipeline.sh` steps without executing; verify each script exists and inputs/outputs wire up |
| `/review-slides` | Once PPTX exists: check slide count vs `SLIDES_OUTLINE.md`, metric accuracy, cost/architecture consistency with report |
| `/cost-audit` | BUSINESS ANALYST sweep: validate $/day claim against EC2 + S3 + GH Actions + egress |
| `/security-review-infra` | Review `infra/*.tf` + `.env*` + IAM policy for least-privilege + secrets hygiene |
| `/status-refresh` | Update `06_Handoff/CAAS_STATUS.md` with a new dated session entry |
| `/drift-snapshot` | Run `evidently_report.py` against the newest features and summarize core vs soft drift counts |

---

## 7. Red flags (visible from file structure alone)

1. **`.env` committed to repo root.** Verify `.gitignore` excludes it and no real keys exist in git history. `.env.example` is the correct template.
2. **`FINALSUBMIT/` contains PROPOSAL PDFs**, not final-submission artifacts. Naming is misleading — easy for graders (or a rushed Supanut) to submit the wrong folder. Rename or clarify.
3. **`02_Presentation/` empty.** Orphan legacy folder; new deliverables are in `07_Final/slides/`. Remove or add a `README.md` redirect.
4. **`07_Final/video/` empty.** Video is a required deliverable per `final_ref.md`.
5. **`07_Final/slides/` has only `SLIDES_OUTLINE.md`** — no `.pptx`, `assets/` empty, `exports/` empty. Presentation scores 15% and is currently 0.
6. **Terraform never applied.** `infra/main.tf` defines S3+IAM+SG+EC2 but there's no `.terraform/` state, no live bucket, no EC2 host. The final report likely references "deployed on AWS" — verify the wording isn't over-claiming.
7. **`.github/workflows/daily_pipeline.yml` runs every 3 hours** and references `secrets.AWS_*` + `secrets.FIRMS_MAP_KEY`. If secrets aren't set in GitHub, the workflow fails every 3 hours forever — generating a failure notification trail and a bad signal if the grader inspects Actions history. Confirm either (a) secrets are set and AWS is deployed, or (b) workflow is disabled until then.
8. **`run_pipeline.sh` hardcodes `caas-env/` venv** and `set -e` — any single step failure aborts the rest. Fine for developer runs, but fragile for demo.
9. **`06_Handoff/CAAS_STATUS.md` is 8 days stale** (last entry 2026-04-09 session 2). A lot has landed since (Dockerfile, Terraform, tests, SHAP, Scenario C) but isn't reflected. The "Model Results" table in it still shows OLD numbers (6.11/7.37/8.44) that don't match the current JSON (5.31/6.91/8.34) — internal inconsistency.
10. **Dockerfile copies individual CSVs and the `03_Data/models/` directory at build time.** If models are retrained after the image is built, the container serves stale models until rebuilt. Consider mounting `03_Data/` as a volume or pulling from S3 at start (the Terraform `user_data` does this, but local Docker runs do not).
11. **`progress_report_CAAS.pdf` duplicated at root and in `01_Proposal/`.** Root copy is from 2026-03-27, `01_Proposal/` version is newer. Risk of confusing readers about "which PDF is current."
12. **`lstm_retrain.log` sitting in `04_Scripts/`.** Runtime log committed to source tree — move to a `logs/` folder or gitignore.

---

## 8. Working-style expectations (from prior sessions)

- **⛔ Do NOT touch the final report or presentation slides yet** (set 2026-04-17). `07_Final/report/` and `07_Final/slides/` are frozen until every other project detail is finalized — code, infra, tests, metrics, AWS deploy, CI/CD live runs. Writing prose before the system stabilizes causes rework. Stale metrics in the report are acceptable for now.
- **Thorough audits, not optimistic summaries.** When the user asks "is X okay?", verify against source-of-truth files (JSON, not report tables) before answering.
- **360° gap view before priorities.** Enumerate every gap (broken / missing / weak) across all rubric areas before narrowing.
- **Proactive enhancement suggestions welcome.** User has explicitly asked for them.
- **Keep folder structures clean.** Numbered prefixes, sub-folders by artifact type, README files where helpful.
- **Always update `06_Handoff/CAAS_STATUS.md`** after meaningful audits/decisions/plan changes.

---

## 9. Common tasks — quick reference

```bash
# Full pipeline from scratch (Steps 0–5, no LSTM)
./run_pipeline.sh all

# Individual steps
./run_pipeline.sh 5      # Train XGBoost only
./run_pipeline.sh 6      # Train LSTM (~1–2h)
./run_pipeline.sh api    # Start FastAPI on :8000
./run_pipeline.sh 9      # Run drift monitor

# Tests
pytest                          # From project root; pytest.ini sets testpaths=tests

# Final report recompile
cd 07_Final/report && pdflatex final_report_CAAS.tex && pdflatex final_report_CAAS.tex

# Terraform (NOT YET RUN — needs AWS creds in .env first)
cd infra && terraform init && terraform plan

# Docker
docker build -t caas-api . && docker run -p 8000:8000 caas-api
curl http://localhost:8000/health
```
