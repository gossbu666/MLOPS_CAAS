# CAAS Monitoring Update (2026-04-03)

## Scope
Updated drift monitoring logic in `04_Scripts/monitoring/evidently_report.py` to reduce false alarms from seasonality/sparse features and make exit-code behavior easier to control.

## What Was Changed

### 1) Added a stricter and clearer retrain policy
- Added constants:
  - `ZERO_INFLATION_THRESHOLD = 0.80`
  - `MIN_CORE_DRIFT_FLAGS = 2`
  - `CORE_TRIGGER_FEATURES = {"pm25_lag1", "pm25_roll7_mean"}`
  - `SEASONAL_KS_FEATURES = {"wind_speed", "hotspot_50km", "is_haze_season"}`
  - `NON_TRIGGER_FEATURES = {"is_haze_season"}`
- New retrain decision rule:
  - retrain if `mae_flag` is true, OR
  - `core_drift_count >= 2`, OR
  - `core_drift_count >= 1` AND `soft_drift_count >= 2`.

### 2) Seasonal-aware KS test for seasonal features
- For features in `SEASONAL_KS_FEATURES`, KS reference now uses only training rows with the same month/day as the recent window (if enough rows).
- This avoids treating expected seasonality as concept drift.

### 3) Zero-inflation handling for PSI
- If both train and recent are highly zero-inflated (>= 80% zeros), PSI flag is suppressed for triggering logic.
- This is relevant for sparse event features (e.g., hotspot counts) where PSI can be unstable.

### 4) Improved per-feature drift metadata
- Each feature record in `drift_summary.json` now includes:
  - `ks_reference` (`global` or `seasonal`)
  - `zero_inflated` (boolean)
  - `contributes_to_trigger` (boolean)
- Summary now includes:
  - `core_drift_count`, `soft_drift_count`
  - `core_drift_features`, `soft_drift_features`
  - `seasonal_reference_rows`
  - `policy` object (the exact applied policy)

### 5) Exit code control for local vs CI usage
- Added CLI option: `--strict-exit`
- Behavior:
  - default mode: always exit `0` unless runtime failure
  - strict mode: exit `1` when retraining is recommended

## CLI Usage
- Default (developer-friendly):
  - `python 04_Scripts/monitoring/evidently_report.py`
- CI / pipeline gate:
  - `python 04_Scripts/monitoring/evidently_report.py --strict-exit`
- Optional retrain dispatch remains:
  - `python 04_Scripts/monitoring/evidently_report.py --trigger-retrain --strict-exit`

## Validation Performed
- Static errors: none.
- Runtime checks:
  - Default mode output generated successfully, HTML report saved, `default_exit_code:0`.
  - Strict mode output generated successfully, HTML report saved, `strict_exit_code:1` when drift recommended.

## Notes
- This update does not change model weights or training data.
- It changes only monitoring decision logic and reporting behavior.
