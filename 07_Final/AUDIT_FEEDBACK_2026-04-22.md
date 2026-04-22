# Proposal-Feedback Audit — 2026-04-22

Cross-checks each point in `07_Final/FEEDBACK_FROM_PROPOSAL.md` against the current `07_Final/report/final_report_CAAS.pdf`.

---

## ✅ Already addressed (keep as-is or light polish)

### 1. Drift/retraining story unified
- §4.4 lists retrain.yml stages: data snapshot → feature build → model train → **validation gate (blocking)** → MLflow register → deploy.
- §4.5 defines PSI > 0.20 and KS p < 0.05 thresholds with seasonal KS references for wind_speed, hotspot_50km, is_haze_season.
- Retrain trigger policy (7-day rolling MAE > 15, or both core features drift, or 1 core + 2 soft features drift) is explicit.
- Zero-inflation PSI suppression for sparse FIRMS features in rainy season is documented.

### 4. Evaluation rigor per horizon
- §3.4 tables split MAE/RMSE/R²/AUROC per horizon t+1/t+3/t+7.
- §3.6 Scenario C has per-horizon PR curves + optimal thresholds.
- §3.7 SHAP summaries per horizon.
- §4.4 validation gate is per-horizon criterion.

### 6. Contribution framing (integration, not methodological novelty)
- §1 Executive Summary opens with "end-to-end MLOps pipeline", not novel model claim.
- §6.1 principal findings labels the system "production-ready within its design scope".
- §6.2 LSTM underperformance at t+3 is called out as a limitation, not hidden.

### 7. GitHub Actions stages, blocking step, charge
- §4.4 enumerates the 5 retrain.yml stages and names validation gate as blocking.
- §5.4 cost table explicitly calls out GitHub Actions: "2,000 min/month free; public repo = unlimited; private ≈160 min used".

---

## 🟡 Partially addressed — tighten during refresh

### 3. Cost realism given always-on serving
Professor specifically asked: *"FastAPI, Streamlit, MLflow, Evidently AI make the deployment story somewhat heavier than the very low monthly budget suggests"*.

Current §5.4 mentions co-location on one t3.micro and spot/stop-idle options, but doesn't directly answer the always-on concern. **Add a paragraph**:
> "All four always-on services co-locate on a single 2 vCPU / 2 GB instance. Each uses `--workers 1` and a 2 GB swap file keeps peak RSS within the free-tier envelope. Evidently runs as an on-demand CLI from GH Actions, not as a persistent web service — so effectively only FastAPI + Streamlit + MLflow are truly always-on. MLflow is a read-only UI (gunicorn 1 worker ≈ 80 MB)."

Also update: **the live box is t3.small (2 GB)**, not t3.micro (1 GB) as written in §5.2/§5.4. Update that line.

---

## ❌ Can't verify yet — slides don't exist

### 2. Report ↔ slides consistency (drift logic, cost, monitoring story)
### 5. Unify data source description across report and slides

Defer to the PPTX build phase (#3 in our todo list). When building the deck, cross-check:
- **Cost figure**: slides must show the same `~$8/month on-demand` or `<$1/month with Learner Lab` as §5.4.
- **Data sources**: PCD PM2.5 Excel + Open-Meteo forecast API + NASA FIRMS — all three named identically.
- **Drift logic**: PSI > 0.20 + KS p < 0.05 + 7-day MAE > 15 thresholds should appear the same way on the slide as in §4.5.

---

## Summary

| # | Feedback point | PDF coverage | Action |
|---|----|----|----|
| 1 | Unified drift/retraining story | ✅ clear | no-op |
| 2 | Report↔slides consistency | ⏳ N/A (no slides) | defer to PPTX build |
| 3 | Cost realism with always-on services | 🟡 partial | **add a paragraph + switch t3.micro→t3.small** |
| 4 | Evaluation rigor per horizon | ✅ clear | no-op |
| 5 | Data source consistency | ⏳ N/A | defer to PPTX |
| 6 | Contribution framing (integration vs novelty) | ✅ clear | no-op |
| 7 | GH Actions stages + blocking + cost | ✅ clear | light polish only |

Only **1 new paragraph** and **1 EC2 size correction** are needed to fully close the feedback loop before slides.
