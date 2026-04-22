# Slide 1: XGBoost wins MAE at all three horizons

**Visual: grid-3x2-image-top-6-body-a**

[Column 1: XGBoost — Champion]
MAE 5.31 / 7.08 / 8.90
- 45 engineered features
- Alert F1 0.84 at t+1
- Promoted via ≥5 % MAE gate
[Image: MAE bar chart — XGBoost vs LSTM]

[Column 2: LSTM — Comparison]
MAE 6.67 / 8.87 / 8.06
- Sequence model (keras)
- Wins only t+7 R²
- Same 2011–2025 dataset
[Image: LSTM test loss curve]

[Column 3: Chronological split]
Train 2011–2022 · Val 2023 · Test 2024–2025
- No leakage by construction
- Lag + rolling features only
- 103 Optuna trials per horizon
[Image: Timeline of data splits]
