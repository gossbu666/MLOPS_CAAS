# CAAS Final Presentation — Slide Outline

**Target:** 10 minutes talk + 5 minutes Q&A
**Format:** PPTX (`CAAS_final.pptx`) exported to PDF in `exports/`

## Slide Plan (14 slides, ~40 sec/slide)

| # | Slide | Content | Time |
|---|-------|---------|------|
| 1 | Title | CAAS logo, authors, course, AIT | 20s |
| 2 | The Problem | Chiang Mai haze crisis — 1 photo + 1 stat | 40s |
| 3 | Objectives | 3 bullet points (forecast, alert, MLOps) | 30s |
| 4 | System Architecture | `fig_cloud_architecture.png` — walk through it | 60s |
| 5 | Data Pipeline | 3 sources → features → 45 features table preview | 60s |
| 6 | Feature Engineering | Top 10 features bar chart (fig_feature_importance.png) | 45s |
| 7 | Models Compared | XGBoost vs LSTM vs Persistence — 3-column table (CORRECTED numbers) | 60s |
| 8 | Best Result | Actual vs predicted plot (fig_actual_vs_predicted.png) | 45s |
| 9 | FIRMS Ablation | Bar chart (fig_firms_ablation.png) — "fire features matter" | 45s |
| 10 | MLOps Stack | Daily pipeline + retrain loop diagram | 60s |
| 11 | Monitoring & Drift | Evidently dashboard screenshot + seasonal policy | 45s |
| 12 | **LIVE DEMO** | Streamlit dashboard → FastAPI → MLflow UI | 180s |
| 13 | Cost & Scalability | Cost table ($/day), scalability notes | 45s |
| 14 | Conclusion + Q&A | 3 takeaways + future work + thank you | 45s |

## Demo Flow (3 min)

1. **Streamlit dashboard** (`localhost:8501`) — show today's forecast + alert
2. **FastAPI `/forecast`** — curl hit in terminal, show JSON response
3. **MLflow UI** (`localhost:5000`) — show CAAS-XGBoost runs, compare metrics
4. **Drift report HTML** — open latest Evidently report, highlight PSI flags
5. **GitHub Actions tab** — show latest daily_pipeline.yml run (green)

## Design Principles

- **One idea per slide** — don't cram
- **Screenshots > text** — visual evidence of working system
- **CORRECTED numbers only** — do NOT use progress report's inflated R² values
- **Demo is the killer moment** — rehearse it 3+ times

## Assets needed

Copy these from `01_Proposal/` to `07_Final/slides/assets/`:
- fig_cloud_architecture.png
- fig_daily_pipeline.png
- fig_model_promotion.png
- fig_mlflow_runs.png
- fig_streamlit_dashboard.png
- fig_drift_output.png
- fig_actual_vs_predicted.png
- fig_feature_importance.png
- fig_firms_ablation.png
- fig_haze_breakdown.png

Plus NEW:
- screenshot of AWS console (S3 bucket + EC2 instance) after deployment
- screenshot of GitHub Actions green build
- SHAP summary plot (once generated)
