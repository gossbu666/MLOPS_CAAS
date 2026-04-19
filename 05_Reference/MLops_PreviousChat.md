# CLAUDE.md — ChiangMai Air Quality Alert System
> Read this file at the start of every session. This is the full project context.

---

## Who I Am
- Name: BOSS (Supanut), student ID st126055
- Graduate student at AIT, course: AT82.02 Data Modeling & Management / MLOps
- Working bilingually — Thai for casual chat, English for technical discussions

## Project Summary
Building an **end-to-end MLOps pipeline** for PM2.5 air quality forecasting in Chiang Mai.
- Forecast PM2.5 concentration **1, 3, and 7 days ahead**
- Trigger automated health alerts when PM2.5 is projected to exceed 50 µg/m³
- Deploy as REST API + Streamlit dashboard
- **Proposal due: March 8, 2026**

---

## Team
| Member | Role |
|--------|------|
| BOSS | ML + Data Engineering (data pipeline, feature engineering, model training, API, dashboard) |
| Friend (Anuj Gupta) | Infrastructure + DevOps (AWS architecture, cost estimate, CI/CD, Evidently monitoring) |

---

## Data Sources — All Confirmed Working

### 1. PM2.5 — air4thai / PCD Thailand
- **Format:** Excel (.xlsx), one file per year, daily averages
- **Coverage:** 2011–2025 (15 years, ~5,475 rows)
- **Files location:** put yearly files in `data/raw/` folder, named `PM2.5(YYYY).xlsx`
- **Chiang Mai stations:**
  - `35T` — City Hall, Chang Phueak **(primary)**
  - `36T` — Yupparaj School, Si Phum (backup, r=0.94 with 35T)
- **Sheet structure:**
  - Sheet "DATA": rows = dates, columns = station IDs (35T, 36T, etc.)
  - Sheet "รายละเอียดจุดตรวจวัด": station metadata
- **Missing rate:** ~2–3% per year (10 missing days in 2025)
- **API:** `http://air4thai.com/forweb/getHistoryData.php` — blocked outside Thailand IP, use for 2021+ data if needed

### 2. Weather — Open-Meteo
- Free API, no key required
- Variables: wind speed, wind direction, humidity, temperature, boundary layer height
- Already tested and working ✅

### 3. Fire Hotspots — NASA FIRMS
- API key available (already tested)
- Northern Thailand bounding box
- 181 hotspots detected in test run ✅
- Variables: fire_count, FRP (Fire Radiative Power)

---

## Scripts — All in Project Folder

| File | Purpose | Status |
|------|---------|--------|
| `build_dataset.py` | Parse Excel ZIPs → ML-ready CSV (44 features) | ✅ Tested |
| `fetch_pm25.py` | Fetch PM2.5 from air4thai API (run on Thai IP) | ✅ Ready |
| `merge_pm25.py` | Merge ZIP + API data sources | ✅ Ready |
| `fetch_airquality.py` | Test API connections (Open-Meteo + FIRMS) | ✅ Tested |

### Running the pipeline (start here each session):
```bash
# Step 1: Process all yearly Excel files
python build_dataset.py --folder data/raw/ --report

# Output: data/pm25_daily_chiangmai.csv
# ~5,475 rows × 44 columns, ready for ML
```

---

## Dataset — What build_dataset.py Produces

**44 columns total:**

### Features (32 columns)
- **Lag:** `PM25_lag1/2/3/7/14`
- **Rolling:** `PM25_roll3/7/14/30_mean`, `PM25_roll3/7/14/30_max`, `PM25_roll7/30_std`
- **Time:** `year, month, day, dayofyear, dayofweek, weekofyear, quarter`
- **Cyclical:** `month_sin, month_cos, day_sin, day_cos`
- **Season flags:** `is_haze_season` (Jan–Apr), `is_rainy_season` (May–Oct), `is_cool_season` (Nov–Dec)
- **Regional:** `north_avg_PM25`, `north_max_PM25`, `north_station_count`

### Targets (6 columns)
- `PM25_next1`, `PM25_next3`, `PM25_next7` — regression
- `alert_next1`, `alert_next3` — binary classification (1 = PM2.5 > 50 µg/m³)
- `AQI_cat_next1` — category label

### Still missing (need to add):
- Weather features from Open-Meteo (wind, humidity, temp, boundary layer)
- Fire features from NASA FIRMS (fire_count, frp_sum within 100km of CM)

---

## ML Plan

### Models
| Model | Role | Status |
|-------|------|--------|
| XGBoost | Baseline tabular model | ⏳ Not started |
| LSTM | Primary sequential model (30-day window) | ⏳ Not started |

### Train/Val/Test Split (chronological — NO shuffling)
- Train: 2011–2022
- Validation: 2023
- Test: 2024–2025

### Baseline to beat: R² = 0.70

### Metrics
- Regression: RMSE, MAE, R²
- Classification: Precision, Recall, F1 — **Recall is priority** (missing alert = worse than false alarm)

### Experiment Tracking: MLflow
- Log all hyperparams, metrics, artifacts per run
- Use Model Registry: Staging → Validation → Production

---

## Infrastructure (handled by friend — pending)
- AWS Learner Lab credits available
- Planned: S3 (storage) + Lambda (batch pipeline) + EC2 t3.micro (API serving)
- Cost target: ~$2–8/month
- CI/CD: GitHub Actions
- Monitoring: Evidently AI (drift detection)

---

## Key Data Insights (from 2025 exploration)
- March 2025 avg: **55.1 µg/m³** (haze peak)
- Single-day max: **92.3 µg/m³** (March 23, 2025)
- Days exceeding WHO 15 µg/m³: **59% of year**
- Days exceeding Thailand safe 25 µg/m³: **31% of year**
- 35T vs 36T correlation: **r = 0.940** (stations very consistent)
- File format note: earlier years (2011–2017) may have different column structure — validate before merge

---

## Current Status
| Component | Status |
|-----------|--------|
| PM2.5 data (2011–2025) | ✅ Have all files locally |
| Data pipeline script | ✅ Done, tested on 2025 |
| Open-Meteo integration | ✅ Tested |
| NASA FIRMS integration | ✅ Tested |
| Weather + FIRMS merge into dataset | ⏳ Next step |
| XGBoost baseline model | ⏳ Not started |
| LSTM model | ⏳ Not started |
| MLflow setup | ⏳ Not started |
| FastAPI endpoint | ⏳ Not started |
| Streamlit dashboard | ⏳ Not started |
| Proposal doc (due Mar 8) | ✅ Draft complete (proposal_final.md) |
| AWS infra + cost | 🔄 Friend working on it |

---

## Immediate Next Steps
1. Add weather features (Open-Meteo) into `build_dataset.py`
2. Add fire features (NASA FIRMS) into `build_dataset.py`
3. Run full pipeline on all 15 years of data
4. Train XGBoost baseline
5. Train LSTM
6. Compare vs R²=0.70 baseline
