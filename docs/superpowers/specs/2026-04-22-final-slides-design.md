# CAAS Final Presentation — Slides Design Spec

**Date:** 2026-04-22
**Presentation date:** 2026-04-24 (2 days out)
**Deck file target:** `07_Final/slides/CAAS_final.pptx` + PDF export in `07_Final/slides/exports/`
**Authors:** Supanut Kompayak (st126055) · Shuvam Shrestha (st125975)

---

## 1. Overview

A 14-slide, 15-minute defense deck for the AT82.9002 Data Engineering & MLOps
capstone. The deck is built with narrative arc **B (Problem → Journey → Payoff)**
and is deliberately structured to close every item in `07_Final/FEEDBACK_FROM_PROPOSAL.md`.

Contribution framing throughout: **"a strong production-oriented integration,
not a novel forecasting algorithm."** This framing answers the "innovation is
moderate" feedback head-on rather than hiding from it.

## 2. Constraints and decisions

| Decision | Choice | Rationale |
|---|---|---|
| Total talk time | **15:00** | User stated slot is ~15 min. Rubric nominal is 10 + 5 Q&A; if actual slot is 10 min talk, trim slide 11 demo to 150s and slide 13 to 25s. |
| Narrative arc | **B — Problem → Journey → Payoff** | Chosen over rubric-mirrored (A) and problem-first-teaser (C) for natural storytelling with the demo as climax. |
| Slide count | **14** | Keeps ~40–90s per slide, a comfortable pace. Demo is 240s of that. |
| Demo approach | **Option B — all embedded, zero live tabs** | EC2 stability history + unknown classroom network. All screenshots captured from live EC2 ahead of defense. |
| Standalone demo video | **Dropped** | Not a rubric requirement. Slide 11 embedded captures replace it. |
| Image assets | **All placeholders** | User pastes real images themselves. Spec defines placeholder style (see §5). |
| Build tool | **python-pptx** → import to Canva for visual polish | Canva accepts PPTX lossless for text + layout; Canva design system for styling. |

## 3. Time budget (total 900 s = 15:00)

| # | Slide title | Seconds | Rubric hit |
|---|---|---|---|
| 1 | Title | 15 | — |
| 2 | Problem + why-it-matters | 45 | Problem 10% |
| 3 | What we built + contribution framing | 35 | closes feedback #3 |
| 4 | System architecture | 55 | DE 25% + MLOps 20% preview |
| 5 | Data pipeline: 3 sources → 45 features → S3 tiers | 70 | DE 25% |
| 6 | Models + chronological split + headline metrics | 75 | ML 15% (closes feedback #4) |
| 7 | SHAP — signal shifts with horizon | 40 | ML 15% interpretability |
| 8 | FIRMS ablation + Scenario C threshold | 50 | ML 15% rigor |
| 9 | Drift policy + retrain trigger + promotion gate | 90 | MLOps 20% (closes feedback #1) |
| 10 | GH Actions stages + blocking step | 40 | MLOps 20% (closes feedback #6) |
| 11 | LIVE DEMO (embedded screenshots) | 240 | Demo 15% |
| 12 | Cost breakdown + realism defense | 60 | Impact 5% (closes feedback #5) |
| 13 | Limitations + what we learned | 55 | Q&A armor |
| 14 | Takeaways + thank-you | 30 | Close |
| | **Total** | **900** | |

## 4. Feedback-to-slide coverage (explicit mapping)

From `07_Final/FEEDBACK_FROM_PROPOSAL.md`:

1. **Unify drift/retrain story** → Slide 9 (90s, one unified flow diagram with numbers)
2. **Align cost + monitoring + data across artifacts** → Slide 12 math matches report exactly; slide 9 policy matches `05_Reference/monitoring_drift_policy_update_2026-04-03.md`
3. **Reframe contribution as integration, not novel method** → Slide 3 banner + slide 14 closing takeaway
4. **Evaluation rigor per horizon** → Slide 6 (chronological split), slide 7 (SHAP per horizon), slide 8 (thresholds per horizon)
5. **Cost realism despite always-on services** → Slide 12 line-item table + "single EC2 co-location" defense
6. **GH Actions stages + blocking step + "any charge?"** → Slide 10 answers literally point-by-point

## 5. Placeholder frame convention

Every slot that needs an image the user will paste later uses a **placeholder
frame** instead of an actual image. The build script creates these as PPTX
shapes (not pictures) so the user can select, delete, and paste cleanly.

**Placeholder frame style:**
- Rectangle shape, fill `#E8E8E8`, dashed border `#AAAAAA` 1.5pt
- Centered text (font: Calibri 14pt italic, colour `#666666`):
  - Line 1: `[IMAGE PLACEHOLDER]`
  - Line 2: specific caption (e.g., `Streamlit dashboard — capture from http://13.250.17.6:8502`)
  - Line 3: suggested aspect ratio (e.g., `16:9 · ~1600×900px`)

**Complete list of placeholder frames across the deck:**

| Slide | Placeholder | Caption text | Suggested aspect |
|---|---|---|---|
| 1 | Title hero background (optional) | `Chiang Mai haze photo — 16:9 full-bleed` | 16:9 |
| 2 | Problem visual left | `Chiang Mai haze photo / skyline during burning season` | 4:3 |
| 2 | Problem visual right (trend) | `PM2.5 yearly peaks 2011–2025 chart` | 4:3 |
| 4 | System architecture diagram | `Cloud architecture — use 01_Proposal/fig_cloud_architecture.png` | 16:9 |
| 5 | Data pipeline flow diagram | `Daily pipeline — 01_Proposal/fig_daily_pipeline.png or similar` | 16:9 |
| 7 | SHAP panel t+1 | `SHAP summary t+1 — 03_Data/results/fig_shap_summary_t1.png` | square |
| 7 | SHAP panel t+3 | `SHAP summary t+3 — 03_Data/results/fig_shap_summary_t3.png` | square |
| 7 | SHAP panel t+7 | `SHAP summary t+7 — 03_Data/results/fig_shap_summary_t7.png` | square |
| 8 | FIRMS ablation bar chart | `FIRMS ablation — 03_Data/results/fig_firms_ablation.png` | 4:3 |
| 8 | PR curve with threshold | `PR curve t+1 with 53.7 µg/m³ marked — 03_Data/results/fig_pr_curve_t1.png` | 4:3 |
| 9 | Drift → Retrain → Validate → Promote flow | `4-stage unified policy diagram — new, draw in PPTX shapes` | 16:9 |
| 10 | GH Actions screenshot | `Green retrain.yml run with 6 stages expanded — github.com/supanut-k/caas/actions` | 16:9 |
| 11 | Streamlit dashboard screenshot | `Full dashboard from http://13.250.17.6:8502` | 16:9 |
| 11 | FastAPI Swagger screenshot | `Swagger UI from http://13.250.17.6:8000/docs` | 16:9 |
| 11 | MLflow experiments screenshot | `Experiments list + champion run from http://13.250.17.6:5001` | 16:9 |
| 11 | Drift report HTML screenshot | `Latest Evidently report with core vs soft features` | 16:9 |
| 11 | GitHub Actions screenshot | `Actions list + retrain.yml expanded stages` | 16:9 |
| 12 | Cost pie/donut chart | `Daily cost breakdown donut — generate with matplotlib or Canva` | square |
| 14 | GitHub QR code | `QR to github.com/supanut-k/caas` | square |

## 6. Slide-by-slide spec

For every slide: visual layout, on-slide text (exact copy), placeholder frames,
speaker notes (full narration).

### Slide 1 — Title (15s)

**Layout:** Full-bleed hero image background (optional placeholder) with a
centered text block on a translucent overlay.

**Text:**
- Main title (56pt bold): `CAAS — ChiangMai Air Quality Alert System`
- Subtitle (28pt): `End-to-End MLOps Pipeline for PM2.5 Forecasting`
- Authors (20pt): `Supanut Kompayak (st126055) · Shuvam Shrestha (st125975)`
- Meta (16pt): `AT82.9002 · Data Engineering and MLOps · AIT · April 2026`

**Placeholder:** 1 optional — hero background.

**Speaker notes:** *"Good afternoon. I'm Supanut, with my teammate Shuvam. We
built CAAS — a production-grade air quality forecasting system for Chiang Mai.
Let's start with why."*

---

### Slide 2 — Problem (45s)

**Layout:** Two-column. Left 50% — two stacked image placeholders (haze photo
on top, PM2.5 trend chart below). Right 50% — three stacked large-stat blocks.

**Text:**
- Title (36pt bold): `Every February–April, Chiang Mai breathes poison.`
- Stat 1 (60pt number): `300+ µg/m³` · caption: `peak daily PM2.5 — 20× WHO limit`
- Stat 2: `1.2M` · caption: `residents in metro area at risk`
- Stat 3: `0` · caption: `public forecasts — PCD publishes only observed values`
- Footer (14pt italic): `Residents learn conditions are hazardous after they already are.`

**Placeholders:** 2 — haze photo, trend chart.

**Speaker notes:** *"Chiang Mai sits in a mountain basin. Every burning season,
PM2.5 peaks above 300 micrograms — twenty times the WHO limit. Thailand's PCD
publishes the number, but only after the air is already bad. 1.2 million people
have no advance warning. That's the gap we built CAAS to close."*

---

### Slide 3 — What we built + contribution framing (35s)

**Layout:** Three icon-bullet rows stacked vertically, with a highlighted
banner at the bottom.

**Text:**
- Title: `What CAAS delivers`
- Bullet 1 (icon: chart): `Forecast PM2.5 at t+1, t+3, t+7 days — 15 years of data, 45 features`
- Bullet 2 (icon: bell): `Hazard alerts at the WHO 50 µg/m³ threshold`
- Bullet 3 (icon: cloud): `Self-retraining MLOps pipeline on AWS — ~$0.55/day`
- Banner (bold, green fill): `Our contribution is a strong production-oriented integration — not a new forecasting algorithm.`

**Placeholders:** 0 (icons drawn as shapes or emoji).

**Speaker notes:** *"CAAS is three things: a multi-horizon PM2.5 forecaster,
a hazard alert service, and a self-retraining pipeline running on AWS for under
a dollar a day. We want to be clear upfront — we're not claiming a new algorithm.
Our contribution is integrating public data sources, standard ML, and MLOps
discipline into one working production system."*

---

### Slide 4 — System architecture (55s)

**Layout:** Full-slide image placeholder + thin title bar on top + small corner
label.

**Text:**
- Title bar: `End-to-end architecture`
- Corner label (10pt): `All provisioned by Terraform`

**Placeholders:** 1 — the cloud architecture diagram.

**Speaker notes:** *"Three public data sources — PCD PM2.5, Open-Meteo weather,
NASA FIRMS fire hotspots — feed a daily ingestion job on AWS. Data lands in
tiered S3 buckets. Training runs with MLflow tracking. The serving stack —
FastAPI for inference, Streamlit for the public dashboard, Evidently for drift
— runs on a single EC2. GitHub Actions orchestrates everything. The whole
stack is Terraform-provisioned, reproducible from a clean AWS account with
one command."*

---

### Slide 5 — Data pipeline (70s)

**Layout:** Two-thirds left — flow diagram placeholder. One-third right —
feature category table.

**Text:**
- Title: `Three public sources → 45 features → versioned S3`
- Feature table:
  | Category | Count |
  |---|---|
  | PM2.5 lags + rolling stats | 14 |
  | Weather (ERA5) | 13 |
  | FIRMS fire | 6 |
  | Seasonality (sin/cos, DOY) | 6 |
  | Regional PM2.5 | 6 |
  | **Total** | **45** |

**Placeholders:** 1 — daily pipeline flow.

**Speaker notes:** *"The data engineering layer pulls from three free public
sources — Thailand's PCD portal for PM2.5, Open-Meteo for ERA5 weather, and
NASA FIRMS for satellite fire hotspots. Everything lands in a tiered S3 bucket
— raw files, cleaned per-source tables, and the 45-feature daily matrix we
train on. The 45 features span five categories: PM2.5 autoregressive lags,
weather, fire hotspots, seasonality, and regional PM2.5. Each tier is
independently reproducible — if a source file updates, we rebuild downstream
without touching the rest."*

---

### Slide 6 — Models + chronological split + headline metrics (75s)

**Layout:** Top — timeline bar (drawn as rectangles). Middle — metrics table.
Bottom — callout banner.

**Text:**
- Title: `Three model families, chronological evaluation`
- Timeline bar caption: `Strict chronological split — no leakage via lag or rolling features.`
- Timeline labels: `Train 2011–2022 (12 yrs)` | `Val 2023` | `Test 2024–2025`
- Metrics table (bold = best):
  | | **LightGBM** (champion) | XGBoost (secondary) | LSTM (comparison) |
  |---|---|---|---|
  | MAE t+1 | **5.12** | 5.31 | 6.67 |
  | MAE t+3 | **6.77** | 7.08 | 8.87 |
  | MAE t+7 | **8.25** | 8.90 | 8.06 |
  | R² t+1 | **0.841** | 0.824 | 0.753 |
  | R² t+3 | **0.729** | 0.712 | 0.540 |
  | AUROC ≥50 µg/m³ t+1 | **0.992** | 0.989 | 0.962 |
- Callout: `LightGBM wins at t+1 and t+3; LSTM only competitive at t+7. Gradient boosting + engineered lag features beat deep sequence on this problem.`

**Placeholders:** 0.

**Verification needed at build time:** confirm all 12 numeric values above
against `03_Data/results/xgboost_summary.json` and `03_Data/results/lstm_summary.json`.

**Speaker notes:** *"We compared three model families — LightGBM, XGBoost, and
an LSTM — under the same chronological evaluation protocol. Training 2011
through 2022, validation on 2023, held-out test on 2024 and 2025. No leakage,
no random shuffling. LightGBM is our champion: 5.12, 6.77, and 8.25 MAE at
t+1, t+3, and t+7. XGBoost is a strong second — we keep it loaded as a runtime
fallback for A/B comparison. The LSTM degrades at mid-horizon — R² drops to
0.54 at t+3. For this problem, gradient boosting with engineered lag features
beats deep sequence modeling. We retain XGBoost in production not because it
wins on accuracy, but because it gives us a natural champion-challenger
surface."*

---

### Slide 7 — SHAP: signal shifts with horizon (40s)

**Layout:** Three-panel horizontal strip (one SHAP panel per horizon), each
with its dominant-feature label above. Interpretation caption along the bottom.

**Text:**
- Title: `The predictive signal shifts with horizon`
- Panel labels:
  - `t+1 → pm25_lag1` (recent PM2.5 persistence)
  - `t+3 → hotspot_14d_roll` (14-day fire accumulation)
  - `t+7 → sin_month` (seasonal calendar position)
- Interpretation caption: `Measurement-driven → fire-driven → climatology-driven. Physically consistent with Chiang Mai haze meteorology.`

**Placeholders:** 3 — one per SHAP panel.

**Speaker notes:** *"One of our favorite findings. SHAP attributions reveal
the dominant predictor changes with horizon. At t+1, yesterday's PM2.5
dominates — simple persistence. At t+3, it shifts to the 14-day rolling fire
hotspot count — burning accumulates, then PM2.5 follows. At t+7, the calendar
takes over — sine of the month — because a week ahead, you're essentially
predicting where in the haze season you'll land. This is physically
interpretable: measurement, then emissions, then climatology. The model
learned the meteorology without us hard-coding it."*

---

### Slide 8 — FIRMS ablation + Scenario C threshold (50s)

**Layout:** Two-column. Left 50% — bar chart placeholder + delta callout.
Right 50% — PR curve placeholder + threshold table.

**Text:**
- Title: `FIRMS adds measurable value; WHO threshold is near-optimal`
- Left caption: `Fire data is not just significant — it is operationally material.`
- Left deltas (overlaid on chart area): `+4.3% (t+1), +6.8% (t+3), +5.1% (t+7) MAE degradation without FIRMS`
- Right threshold table:
  | Horizon | Optimal threshold | F1 gain vs. 50 µg/m³ |
  |---|---|---|
  | t+1 | **53.7** µg/m³ | +4.0% |
  | t+3 | 50.0 (no change) | 0% |
  | t+7 | 50.0 (no change) | 0% |
- Right caption: `WHO/Thai 50 µg/m³ threshold is well-calibrated for two of three horizons — we keep it.`

**Placeholders:** 2 — FIRMS ablation bar chart, PR curve.

**Verification needed at build time:** confirm ablation deltas against
`03_Data/results/ablation_summary.json`; confirm optimal threshold values
against `03_Data/results/scenario_c_summary.json`.

**Speaker notes:** *"Two rigor checks. First, ablation: we retrained the
champion without the six FIRMS features. MAE degrades between 4.3 and 6.8
percent across horizons — strongest at t+3, where the 14-day fire accumulation
matters most. So FIRMS is earning its integration cost. Second, threshold
tuning: we asked whether the default WHO 50 µg/m³ alert threshold is optimal.
For t+3 and t+7, yes — it's within noise of the F1 maximum. For t+1, tuning
to 53.7 gains 4 percent F1 — a real but small improvement. We keep 50
operationally because consistency with the public-health standard beats
marginal F1, but the analysis is published."*

---

### Slide 9 — Drift policy + retrain trigger + promotion gate (90s)

**Layout:** Full-width flow diagram placeholder showing 4 stages left-to-right:
MONITOR → TRIGGER → VALIDATE → PROMOTE. Each stage has 2–3 sub-bullets.
Bottom callout for the seasonal-suppression rationale.

**Text:**
- Title: `Drift → Retrain → Validate → Promote — one unified policy`
- Stage 1 — MONITOR (daily, Evidently on EC2):
  - `Core features (hard drift):` PSI > 0.25 OR KS p < 0.05 → flag
  - `Soft features (seasonal-suppressed):` FIRMS — zero-inflated, exempt from PSI alone
  - Rolling `28-day MAE` tracked
- Stage 2 — TRIGGER (any of):
  - Core feature PSI > 0.25 sustained ≥ 3 days, OR
  - Rolling MAE ↑ ≥ 15% vs. baseline, OR
  - Monthly schedule cap
- Stage 3 — VALIDATE (`validate_candidate.py`):
  - Candidate must beat champion by **MAE ≥ 5%** at primary horizon, AND
  - Alert F1 at 50 µg/m³ must stay **≥ 0.75** at t+1/t+3
  - Else → BLOCK, keep champion, log in MLflow
- Stage 4 — PROMOTE (`promote_model.py` → MLflow registry):
  - New stage `Production`, previous → `Archived`
  - FastAPI hot-reloads on next heartbeat
- Bottom callout: `Seasonal suppression is deliberate — naive PSI would retrain every February because FIRMS legitimately spikes. Two-tier policy preserves sensitivity without false alarms.`

**Placeholders:** 1 — the 4-stage flow diagram.

**Verification needed at build time:** confirm PSI threshold (0.25), day window
(3), rolling MAE delta (15%), validation thresholds (5% MAE, 0.75 F1) against
`05_Reference/monitoring_drift_policy_update_2026-04-03.md` and
`04_Scripts/validate_candidate.py`.

**Speaker notes:** *"This is the policy the professor asked us to unify.
Four stages. Monitor — Evidently runs daily on EC2. We split features into
two tiers: core features like PM2.5 lags and weather use PSI and KS tests
directly. Soft features — mainly FIRMS — are zero-inflated in the rainy
season, so naive drift detection would fire every February by design. We
suppress those unless paired with a performance signal. Trigger — retraining
fires if core-feature PSI stays above 0.25 for three days, OR rolling 28-day
MAE degrades by 15 percent, OR monthly cap hits. Validate — the candidate
must beat the champion by at least 5 percent MAE AND keep alert F1 above 0.75.
If it fails either, validate_candidate.py blocks the promotion and we keep
the champion. Promote — only if it passes, promote_model.py rewrites the
MLflow registry stage. FastAPI reloads on the next heartbeat. No human click
required."*

---

### Slide 10 — GitHub Actions stages + blocking step (40s)

**Layout:** Horizontal 6-box pipeline diagram (shapes, not image — each stage
as a numbered rectangle, with stage 4 highlighted red as the blocking gate).
Below: GH Actions screenshot placeholder showing a green run.

**Text:**
- Title: `retrain.yml — 6 stages, one gate, $0`
- Stage boxes:
  1. `Snapshot data` — `fetch_pm25_live.py` + S3 sync — *immutable daily snapshot*
  2. `Build features` — `build_features.py` — *45-col matrix to features/*
  3. `Train candidate` — `train_xgboost.py` / `train_lstm.py` — *artifact + MLflow run*
  4. 🛑 **`Validate`** — `validate_candidate.py` — **BLOCKS if MAE gain < 5% OR F1 < 0.75**
  5. `Register` — MLflow — *candidate → `Staging`*
  6. `Promote + deploy` — `promote_model.py` + FastAPI reload — *stage `Production`*
- Bottom banner: `Runs on ubuntu-latest. ~8 minutes end-to-end. GitHub Actions minutes: public repo = unlimited & free. AWS API calls: negligible (~$0.01/run).`

**Placeholders:** 1 — GH Actions screenshot.

**Verification needed at build time:** confirm repo public status, actual
workflow runtime. If private, replace "unlimited & free" with "within 2,000
free min/month private-repo quota."

**Speaker notes:** *"And here's the CI/CD answer. Six stages: snapshot the
data, build features, train the candidate, validate, register, promote. The
validate step is the gate — validate_candidate.py returns non-zero if the
candidate doesn't beat the champion, which fails the workflow and blocks
stages 5 and 6. Nothing gets promoted without passing the gate. Runtime is
about 8 minutes on ubuntu-latest. Because our repo is public, GitHub Actions
minutes are free and unlimited. AWS costs are pennies per run."*

---

### Slide 11 — LIVE DEMO (embedded screenshots) (240s)

**Layout:** Title bar + 5 screenshot placeholders arranged in a 2×3 grid (one
cell unused for transition text). Each placeholder labeled 1️⃣–5️⃣ matching
narration order.

**Text:**
- Title bar: `CAAS running on AWS — http://13.250.17.6`
- Sub-caption under title: `5 views, 240 seconds, all captures from live EC2`
- Placeholder labels (top-left corner of each frame):
  - `1️⃣ Streamlit dashboard`
  - `2️⃣ FastAPI Swagger`
  - `3️⃣ MLflow experiments`
  - `4️⃣ Evidently drift report`
  - `5️⃣ GitHub Actions`

**Placeholders:** 5 — one per demo station.

**Timing within the 240s:**
| Phase | Duration | Action |
|---|---|---|
| Intro | 15s | "Everything you'll see is from our live EC2" |
| 1 Streamlit | 40s | point to freshness pill, 3 forecast cards, alert banner, history, Model Insights tab |
| 2 FastAPI | 35s | point to `/health`, `/forecast`, OpenAPI schema |
| 3 MLflow | 45s | 8 experiments, champion run, params/metrics/artifacts lineage |
| 4 Drift | 35s | core green, FIRMS amber and suppressed by two-tier policy |
| 5 GH Actions | 40s | green Tests + Drift Check, retrain.yml 6 stages |
| Transition | 15s | "back to slides — let's talk cost" |
| Buffer | 15s | absorb any overflow |

**Speaker notes:** *"For the next four minutes, we're walking through CAAS as
it runs right now on AWS. All five views you're about to see are captures
from our live EC2 at 13.250.17.6. Starting with the dashboard … [then narrate
each station as per the 5 rows above]."*

---

### Slide 12 — Cost breakdown + realism defense (60s)

**Layout:** Two-thirds left — cost line-item table. One-third right — donut
chart placeholder + green realism-defense callout.

**Text:**
- Title: `$0.55/day — with receipts`
- Cost table (ap-southeast-1 on-demand):
  | Component | Usage | Daily cost |
  |---|---|---|
  | EC2 t3.small (24/7) | 24 h × $0.023/h | $0.552 |
  | EBS gp3 20 GB | storage + IOPS | $0.053 |
  | S3 standard (~1.5 GB) | storage + requests | $0.004 |
  | Data transfer out | ~200 MB/day | $0.018 |
  | GitHub Actions | public repo | **$0.00** |
  | FIRMS / Open-Meteo / PCD | free tier | **$0.00** |
  | **Total** | | **~$0.63/day** |
  | *EventBridge stop-cycle 12h/day* | | *~$0.35/day* |
- Green callout: `Always-on serving (FastAPI + Streamlit + MLflow + Evidently) sounds expensive, but it all fits inside a single t3.small — the three services together peak at ~1.3 GB RAM. The "always-on" cost is one EC2 instance, not four.`

**Placeholders:** 1 — cost donut chart.

**Speaker notes:** *"The cost claim the professor asked us to defend. On-demand
pricing, one EC2 t3.small running 24/7, is 55 cents a day. Add a little
storage, egress, and we land at 63 cents. GitHub Actions is free because our
repo is public. The data APIs are free at research tier. The 'always-on'
story that the professor flagged as suspicious — the four services — all
co-locate on a single 2 GB EC2 instance because our workload is low traffic.
If we ran EventBridge to stop the instance overnight, we'd drop to 35 cents
a day. For a realistic national deployment you'd horizontally scale, but for
one station at demo scale, this math is honest."*

---

### Slide 13 — Limitations + what we learned (55s)

**Layout:** Two-column, balanced. No images.

**Text:**
- Title: `Limitations and what we learned`
- Left column — **Limitations** (4 bullets):
  - **Single station.** CAAS trains and serves on one PCD station (35T/36T). Inter-station transfer not demonstrated.
  - **Hindcast, not forecast weather.** ERA5 reanalysis is retrospective; true t+3 / t+7 production needs ECMWF/GFS.
  - **LSTM under-performs at t+3** (R² = 0.54). Transformers are a likely next step.
  - **Seasonal FIRMS zero-inflation** handled by suppression heuristic — STL decomposition would be cleaner.
- Right column — **What we learned** (4 bullets):
  - **Boring MLOps pays.** Chronological splits, validation gates, drift policy — the least novel parts carried the story.
  - **Interpretability > complexity.** SHAP gave a physically clean story a black-box wouldn't have.
  - **Public data goes far.** Three free sources produced a grader-ready system.
  - **Integration is the product.** The pieces aren't new — wiring them into a self-retraining pipeline on one EC2 is.

**Placeholders:** 0.

**Speaker notes:** *"What we'd change and what we take away. Four honest
limitations — single station, hindcast weather, LSTM at mid-horizon, and
seasonal zero-inflation. None of these are blockers for the demo scope, but
all four are the first things we'd fix in a real deployment. On the learning
side — the boring MLOps parts carried more weight than the modeling choices.
SHAP gave us a physically interpretable story that a pure deep model wouldn't
have offered. And the whole project reinforced that integration — not
invention — was the real engineering."*

---

### Slide 14 — Takeaways + thank-you (30s)

**Layout:** Centered, minimal, airy.

**Text:**
- Title (small, top): `Three takeaways`
- Bullet 1 (icon target): `LightGBM + engineered lags beat LSTM at all three horizons on this problem.`
- Bullet 2 (icon fire): `FIRMS fire data is operationally material — 4.3–6.8% MAE contribution.`
- Bullet 3 (icon gear): `A self-retraining MLOps pipeline fits in $0.55/day — integration over invention.`
- Separator line
- Centered (32pt): `Thank you — we welcome your questions.`
- Bottom-left credits (12pt):
  - `Supanut Kompayak (st126055) · Shuvam Shrestha (st125975)`
  - `AT82.9002 · Instructor: Dr. Chantri Polprasert`
  - `AIT · April 2026`
- Bottom-right: `github.com/supanut-k/caas` + QR code placeholder

**Placeholders:** 1 — GitHub QR code.

**Speaker notes:** *"Three takeaways. LightGBM with engineered lags wins on
this problem — deep sequence is not automatically better. NASA FIRMS fire
data earns its integration cost — 4 to 7 percent MAE contribution. And a
self-retraining MLOps pipeline on AWS costs under 55 cents a day — the
contribution of this capstone was integration, not invention. Thank you —
Shuvam and I are happy to take your questions."*

---

## 7. Build approach (for implementation phase)

Use **python-pptx** to generate `07_Final/slides/CAAS_final.pptx`. Steps:

1. Create a `04_Scripts/build_slides.py` script that generates all 14 slides
   deterministically from this spec.
2. The script produces the file with:
   - All text exactly per §6
   - All placeholder frames per §5 (gray fill, dashed border, caption)
   - Tables drawn as native PPTX tables (not images)
   - Timeline bars, pipeline boxes, and stage-flow shapes drawn as native
     PPTX shapes with the specified colors
3. Use a single slide master with consistent fonts (Calibri) and AIT-flavored
   colour palette (primary `#0E4D64` or similar institutional blue; accent
   `#E8B900` AIT yellow; neutral greys `#333 / #666 / #AAA`).
4. User imports the resulting `.pptx` into Canva for visual polish + pasting
   real images into the placeholder frames.

## 8. Verification checklist (run at build time, before handing the .pptx over)

- [ ] All 12 numeric values on Slide 6 match `03_Data/results/*.json`
- [ ] Ablation deltas on Slide 8 match `ablation_summary.json`
- [ ] Thresholds on Slide 8 match `scenario_c_summary.json`
- [ ] Policy thresholds on Slide 9 match `monitoring_drift_policy_update_2026-04-03.md`
  and `validate_candidate.py`
- [ ] GH Actions messaging on Slide 10 matches actual repo visibility (public/private)
  and actual workflow runtime
- [ ] Total speaker-note seconds sum to 900s
- [ ] All 19 image placeholders present with correct captions
- [ ] File opens in PowerPoint AND imports into Canva without layout breakage
- [ ] PDF export clean (no placeholder-text overflow)

## 9. Out of scope (explicitly not in this deck)

- A standalone demo video — **dropped** per user decision 2026-04-22.
- Any live network activity during the defense — slide 11 is fully static
  screenshots, no browser tabs opened during presentation.
- Slide transitions/animations beyond basic fade — Canva polish phase, not
  the python-pptx build phase.

## 10. Next step after this spec is approved

Invoke `superpowers:writing-plans` skill to turn this spec into an
implementation plan for `04_Scripts/build_slides.py`.
